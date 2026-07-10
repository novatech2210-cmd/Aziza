import {
  WebSocketGateway,
  WebSocketServer,
  OnGatewayConnection,
  OnGatewayDisconnect,
} from '@nestjs/websockets';
import { Server } from 'ws';
import * as WebSocket from 'ws';
import { Logger } from '@nestjs/common';
import Redis from 'ioredis';
import { v4 as uuidv4 } from 'uuid';
import * as jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET;
if (!JWT_SECRET) {
  throw new Error('JWT_SECRET environment variable is required');
}

@WebSocketGateway({
  path: '/api/v2v',
  cors: { origin: '*' },
})
export class V2VGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;

  private readonly logger = new Logger(V2VGateway.name);
  private redis: Redis;
  private clients: Map<string, any> = new Map();
  private workerConnections: Map<string, WebSocket> = new Map();

  constructor() {
    const redisConfig = {
      host: process.env.REDIS_HOST || '127.0.0.1',
      port: parseInt(process.env.REDIS_PORT || '6379'),
      connectTimeout: 10_000,
    };
    this.redis = new Redis(redisConfig);

    this.redis.on('error', (err) =>
      this.logger.error('Redis Error in V2VGateway', err),
    );
  }

  async handleConnection(client: any, request: any) {
    const url = new URL(request.url || '', 'http://localhost');
    const params = Object.fromEntries(url.searchParams.entries());

    // Validate JWT token
    const token = params.token;
    if (!token) {
      this.logger.warn('V2V Connection rejected: no token provided');
      client.send(JSON.stringify({ type: 'error', message: 'Authentication required' }));
      client.close(4001, 'Authentication required');
      return;
    }

    try {
      const payload = jwt.verify(token, JWT_SECRET) as jwt.JwtPayload;
      client.userId = payload.sub || payload.userId;
      client.username = payload.username;
    } catch (err) {
      this.logger.warn(`V2V Connection rejected: invalid token - ${err.message}`);
      client.send(JSON.stringify({ type: 'error', message: 'Invalid or expired token' }));
      client.close(4002, 'Invalid token');
      return;
    }

    const sessionId = params.session_id || uuidv4();
    client.sessionId = sessionId;
    this.clients.set(sessionId, client);
    this.logger.log(`V2V Client connected: ${sessionId} (user: ${client.username || client.userId})`);

    // Assign a GPU worker
    let assignedWorker: string | null = null;
    let assignedWsUrl: string | null = null;

    const luaScript = `
      local status = redis.call('HGET', KEYS[1], 'status')
      if status == 'idle' then
        redis.call('HSET', KEYS[1], 'status', 'busy')
        return 1
      end
      return 0
    `;

    const keys = await this.redis.keys('moshi:workers:*');
    for (const key of keys) {
      const result = await this.redis.eval(luaScript, 1, key);
      if (result === 1) {
        assignedWorker = await this.redis.hget(key, 'worker_id');
        assignedWsUrl = await this.redis.hget(key, 'ws_url');
        break;
      }
    }

    if (!assignedWorker || !assignedWsUrl) {
      this.logger.warn(`No idle workers available for V2V session ${sessionId}`);
      client.send(
        JSON.stringify({
          type: 'error',
          message: 'No GPU workers available. Please try again shortly.',
        }),
      );
      client.close(1013, 'No workers available');
      return;
    }

    client.workerId = assignedWorker;
    this.logger.log(`Assigned worker ${assignedWorker} to V2V session ${sessionId}`);

    // Convert internal Redis URL to localhost if it's the same machine, or use it directly
    // assignedWsUrl is typically "ws://127.0.0.1:8001/ws"
    const workerUrl = `${assignedWsUrl}?session_id=${sessionId}`;
    this.logger.log(`Connecting proxy to Moshi Worker WS: ${workerUrl}`);
    const workerWs = new WebSocket(workerUrl);
    this.workerConnections.set(sessionId, workerWs);

    workerWs.on('open', () => {
      this.logger.log(`Connected to Moshi worker WS for session ${sessionId}`);
      if (client.readyState === 1 /* OPEN */) {
        client.send(JSON.stringify({ type: 'worker_connected', sessionId }));
      }
    });

    workerWs.on('message', (data: WebSocket.Data) => {
      // Forward binary and text responses from Moshi directly to frontend client
      if (client.readyState === 1 /* OPEN */) {
        client.send(data);
      }
    });

    workerWs.on('error', (err) => {
      this.logger.error(`Moshi Worker WS Error for session ${sessionId}: ${err.message}`);
    });

    workerWs.on('close', () => {
      this.logger.log(`Moshi Worker WS closed for session ${sessionId}`);
      if (client.readyState === 1 /* OPEN */) {
        client.close(1011, 'Worker connection lost');
      }
    });

    // Frontend client messages to Worker
    client.on('message', async (payload: Buffer | string | ArrayBuffer | Buffer[]) => {
      try {
        let isText = false;
        let msgString = '';

        if (typeof payload === 'string') {
          isText = true;
          msgString = payload;
        } else if (Buffer.isBuffer(payload)) {
          if (payload[0] === 0x7b) { // '{' -> JSON
            isText = true;
            msgString = payload.toString('utf8');
          }
        }

        if (isText) {
          try {
            const msg = JSON.parse(msgString);
            if (msg.type === 'ping') {
              client.send(JSON.stringify({ type: 'pong', session_id: sessionId }));
              return;
            }
            if (msg.type === 'start_session') {
              if (workerWs.readyState === WebSocket.OPEN) {
                workerWs.send(msgString);
              }
              client.send(
                JSON.stringify({
                  type: 'first_token',
                  session_id: sessionId,
                  language: msg.language || 'ru',
                  measure_ttft: msg.measure_ttft || false,
                }),
              );
              return;
            }
            
            // Forward other JSON messages as text
            if (workerWs.readyState === WebSocket.OPEN) {
              workerWs.send(msgString);
            }
            return;
          } catch (err) {
            this.logger.warn(`Failed to parse JSON text from ${sessionId}`);
          }
        }

        // Forward binary audio payload
        if (workerWs.readyState === WebSocket.OPEN) {
          workerWs.send(payload);
        }
      } catch (e) {
        this.logger.warn(`Failed to process message from ${sessionId}: ${e.message}`);
      }
    });

    client.on('error', (err: Error) => {
      this.logger.error(`Socket error for V2V session ${sessionId}: ${err.message}`);
    });
  }

  async handleDisconnect(client: any) {
    const sessionId = client.sessionId;
    const workerId = client.workerId;

    this.clients.delete(sessionId);
    this.logger.log(`V2V Client disconnected: ${sessionId}`);

    const workerWs = this.workerConnections.get(sessionId);
    if (workerWs) {
      workerWs.close();
      this.workerConnections.delete(sessionId);
    }

    if (workerId) {
      await this.redis.hset(`moshi:workers:${workerId}`, 'status', 'idle');
      await this.redis.publish('orchestrator:session:release', workerId);
      this.logger.log(`Released worker ${workerId} for V2V session ${sessionId}`);
    }
  }
}
