import {
  WebSocketGateway,
  WebSocketServer,
  OnGatewayConnection,
  OnGatewayDisconnect,
} from '@nestjs/websockets';
import { Server } from 'ws';
import WebSocket from 'ws';
import { Logger } from '@nestjs/common';
import Redis from 'ioredis';
import { v4 as uuidv4 } from 'uuid';
import * as jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET;
if (!JWT_SECRET) {
  throw new Error('JWT_SECRET environment variable is required');
}

interface V2VSession {
  sessionId: string;
  userId: string;
  username?: string;
  workerId: string;
  connectedAt: number;
  lastPongAt: number;
  transcript: Array<{ role: string; content: string; ts: number }>;
  audioBytesIn: number;
  audioBytesOut: number;
  messageCount: number;
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
  private sessions: Map<string, V2VSession> = new Map();
  private heartbeatIntervals: Map<string, NodeJS.Timeout> = new Map();

  // Metrics
  private metrics = {
    totalConnections: 0,
    activeConnections: 0,
    totalSessions: 0,
    averageSessionDurationMs: 0,
    sessionsCompleted: 0,
    totalAudioBytesIn: 0,
    totalAudioBytesOut: 0,
    errors: 0,
  };

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
      const payload = jwt.verify(token, JWT_SECRET, { algorithms: ['HS256'] }) as jwt.JwtPayload;
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
    this.metrics.totalConnections++;
    this.metrics.activeConnections = this.clients.size;
    this.metrics.totalSessions++;
    this.logger.log(`V2V Client connected: ${sessionId} (user: ${client.username || client.userId})`);

    // Track session
    const session: V2VSession = {
      sessionId,
      userId: client.userId,
      username: client.username,
      workerId: '',
      connectedAt: Date.now(),
      lastPongAt: Date.now(),
      transcript: [],
      audioBytesIn: 0,
      audioBytesOut: 0,
      messageCount: 0,
    };
    this.sessions.set(sessionId, session);

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
      this.sessions.delete(sessionId);
      this.metrics.errors++;
      return;
    }

    session.workerId = assignedWorker;
    this.logger.log(`Assigned worker ${assignedWorker} to V2V session ${sessionId}`);

    // Connect to Moshi Worker
    const workerUrl = `${assignedWsUrl}?session_id=${sessionId}`;
    this.logger.log(`Connecting proxy to Moshi Worker WS: ${workerUrl}`);
    const workerWs = new WebSocket(workerUrl);
    this.workerConnections.set(sessionId, workerWs);

    // Start heartbeat monitoring (ping every 25s, timeout after 10s)
    const heartbeatInterval = setInterval(() => {
      if (workerWs.readyState === WebSocket.OPEN) {
        workerWs.ping();
      }
    }, 25000);
    this.heartbeatIntervals.set(sessionId, heartbeatInterval);

    workerWs.on('open', () => {
      this.logger.log(`Connected to Moshi worker WS for session ${sessionId}`);
      if (client.readyState === 1 /* OPEN */) {
        client.send(JSON.stringify({
          type: 'worker_connected',
          sessionId,
          workerId: assignedWorker,
        }));
      }
    });

    workerWs.on('message', (data: WebSocket.Data) => {
      // Track outbound audio
      if (Buffer.isBuffer(data) && data[0] === 0x01) {
        session.audioBytesOut += data.length;
        this.metrics.totalAudioBytesOut += data.length;
      }

      // Track text responses for transcript
      if (Buffer.isBuffer(data) && data[0] === 0x02) {
        try {
          const text = data.slice(1).toString('utf-8');
          session.transcript.push({
            role: 'assistant',
            content: text,
            ts: Date.now(),
          });
        } catch { /* non-UTF8 text, skip */ }
      }

      // Forward binary and text responses from Moshi directly to frontend client
      if (client.readyState === 1 /* OPEN */) {
        client.send(data);
      }
    });

    workerWs.on('pong', () => {
      session.lastPongAt = Date.now();
    });

    workerWs.on('error', (err) => {
      this.logger.error(`Moshi Worker WS Error for session ${sessionId}: ${err.message}`);
      this.metrics.errors++;
    });

    workerWs.on('close', (code, reason) => {
      this.logger.log(`Moshi Worker WS closed for session ${sessionId} (code=${code})`);
      clearInterval(heartbeatInterval);
      this.heartbeatIntervals.delete(sessionId);
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
          // Track inbound audio
          if (payload[0] !== 0x7b) { // not '{' — binary audio
            session.audioBytesIn += payload.length;
            this.metrics.totalAudioBytesIn += payload.length;
          }
          if (payload[0] === 0x7b) { // '{' -> JSON
            isText = true;
            msgString = payload.toString('utf8');
          }
        }

        session.messageCount++;

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
            if (msg.type === 'text_request' && msg.text) {
              session.transcript.push({
                role: 'user',
                content: msg.text,
                ts: Date.now(),
              });
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
      this.metrics.errors++;
    });
  }

  async handleDisconnect(client: any) {
    const sessionId = client.sessionId;
    const workerId = client.workerId;
    const session = this.sessions.get(sessionId);

    this.clients.delete(sessionId);
    this.metrics.activeConnections = this.clients.size;

    // Clear heartbeat
    const heartbeatInterval = this.heartbeatIntervals.get(sessionId);
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      this.heartbeatIntervals.delete(sessionId);
    }

    // Close worker connection
    const workerWs = this.workerConnections.get(sessionId);
    if (workerWs) {
      workerWs.close();
      this.workerConnections.delete(sessionId);
    }

    // Persist transcript before cleanup
    if (session && session.transcript.length > 0) {
      try {
        const transcriptKey = `v2v:transcript:${sessionId}`;
        await this.redis.set(transcriptKey, JSON.stringify(session.transcript), 'EX', 86400); // 24h TTL
        this.logger.log(`Persisted transcript for ${sessionId}: ${session.transcript.length} messages`);
      } catch (err) {
        this.logger.error(`Failed to persist transcript for ${sessionId}: ${err.message}`);
      }
    }

    // Update session metrics
    if (session) {
      const durationMs = Date.now() - session.connectedAt;
      this.metrics.sessionsCompleted++;
      this.metrics.averageSessionDurationMs =
        (this.metrics.averageSessionDurationMs * (this.metrics.sessionsCompleted - 1) + durationMs) /
        this.metrics.sessionsCompleted;
      this.sessions.delete(sessionId);
    }

    // Release worker
    if (workerId) {
      await this.redis.hset(`moshi:workers:${workerId}`, 'status', 'idle');
      await this.redis.publish('orchestrator:session:release', workerId);
      this.logger.log(`Released worker ${workerId} for V2V session ${sessionId}`);
    }

    this.logger.log(`V2V Client disconnected: ${sessionId}`);
  }

  getMetrics() {
    return {
      ...this.metrics,
      activeSessions: this.sessions.size,
    };
  }
}
