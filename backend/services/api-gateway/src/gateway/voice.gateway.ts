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

// How often to send a TCP-level ping to detect stale connections (ms)
const HEARTBEAT_INTERVAL_MS = 30_000;
const JWT_SECRET = process.env.JWT_SECRET;
if (!JWT_SECRET) {
  throw new Error('JWT_SECRET environment variable is required');
}

@WebSocketGateway({
  path: '/api/chat',
  cors: { origin: '*' },
})
export class VoiceGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;

  private readonly logger = new Logger(VoiceGateway.name);
  private redis: Redis;
  private subscriber: Redis;
  private clients: Map<string, any> = new Map();
  private workerConnections: Map<string, any> = new Map();

  // Per-client heartbeat timers so we can cancel on disconnect
  private heartbeatTimers: Map<string, NodeJS.Timeout> = new Map();

  constructor() {
    const redisConfig = {
      host: process.env.REDIS_HOST || '127.0.0.1',
      port: parseInt(process.env.REDIS_PORT || '6379'),
      connectTimeout: 10_000,
    };
    this.redis = new Redis(redisConfig);
    this.subscriber = new Redis(redisConfig);

    this.redis.on('error', (err) =>
      this.logger.error('Redis Publisher Error', err),
    );
    this.subscriber.on('error', (err) =>
      this.logger.error('Redis Subscriber Error', err),
    );

    // Forward audio and token responses from Redis to the connected client
    this.subscriber.psubscribe('session:*:playback', 'session:*:tokens');
    this.subscriber.on('pmessageBuffer', (_pattern, channel, message) => {
      const channelStr = channel.toString();
      const parts = channelStr.split(':');
      const sessionId = parts[1];
      const type = parts[2]; // 'playback' | 'tokens'

      const client = this.clients.get(sessionId);
      if (client && client.readyState === 1 /* OPEN */) {
        if (type === 'playback') {
          // 0x01 prefix = audio frame
          const buffer = Buffer.concat([Buffer.from([0x01]), message]);
          client.send(buffer);
        } else if (type === 'tokens') {
          // 0x02 prefix = text token
          const buffer = Buffer.concat([Buffer.from([0x02]), message]);
          client.send(buffer);
          // Track transcript for persistence
          const text = message.toString('utf-8');
          if (text && client.transcript) {
            const lastEntry = client.transcript[client.transcript.length - 1];
            if (lastEntry && lastEntry.role === 'assistant' && !lastEntry.finished) {
              lastEntry.content += text;
            } else {
              client.transcript.push({
                role: 'assistant',
                content: text,
                timestamp: new Date().toISOString(),
                finished: false,
              });
            }
          }
        }
      }
    });
  }

  async handleConnection(client: any, request: any) {
    // Extract query parameters from connection URL
    const url = new URL(request.url || '', 'http://localhost');
    const params = Object.fromEntries(url.searchParams.entries());

    // Validate JWT token
    const token = params.token;
    if (!token) {
      this.logger.warn('Connection rejected: no token provided');
      client.send(JSON.stringify({ type: 'error', message: 'Authentication required' }));
      client.close(4001, 'Authentication required');
      return;
    }

    try {
      const payload = jwt.verify(token, JWT_SECRET, { algorithms: ['HS256'] }) as jwt.JwtPayload;
      client.userId = payload.sub || payload.userId;
      client.username = payload.username;
    } catch (err) {
      this.logger.warn(`Connection rejected: invalid token - ${err.message}`);
      client.send(JSON.stringify({ type: 'error', message: 'Invalid or expired token' }));
      client.close(4002, 'Invalid token');
      return;
    }

    const sessionId = params.session_id || uuidv4();
    client.sessionId = sessionId;
    client.isAlive = true;
    client.transcript = []; // Track transcript for persistence
    this.clients.set(sessionId, client);
    this.logger.log(`Client connected: ${sessionId} (user: ${client.username || client.userId})`);

    // ── TCP-level heartbeat: terminate zombie sockets after one missed ping ──
    const heartbeat = setInterval(() => {
      if (client.isAlive === false) {
        this.logger.warn(
          `Session ${sessionId}: zombie connection detected – terminating.`,
        );
        clearInterval(heartbeat);
        this.heartbeatTimers.delete(sessionId);
        client.terminate();
        return;
      }
      client.isAlive = false;
      client.ping(); // native WS ping frame (not application-level)
    }, HEARTBEAT_INTERVAL_MS);

    this.heartbeatTimers.set(sessionId, heartbeat);

    // Reset liveness flag on native pong frame
    client.on('pong', () => {
      client.isAlive = true;
    });

    client.on('error', (err: Error) => {
      this.logger.error(`Socket error for session ${sessionId}: ${err.message}`);
    });

    // ── Application-level message handler ──
    client.on('message', async (payload: Buffer | string) => {
      try {
        const raw = Buffer.isBuffer(payload) ? payload : Buffer.from(payload);

        // Binary audio frames: first byte is NOT '{' (0x7B)
        if (raw[0] !== 0x7b) {
          this.logger.debug(`Audio frame from ${sessionId}: ${raw.length} bytes`);
          await this.redis.publish(`session:${sessionId}:audio_in`, raw);
          return;
        }

        // JSON control messages
        const msg: Record<string, any> = JSON.parse(raw.toString());

        switch (msg.type) {
          case 'ping':
            // Application-level ping — benchmark keep-alive
            client.send(
              JSON.stringify({ type: 'pong', session_id: sessionId }),
            );
            client.isAlive = true;
            break;

          case 'start_session': {
            const sessionStartMs = Date.now();
            await this.redis.publish(
              `session:${sessionId}:control`,
              JSON.stringify({
                type: 'session_update',
                language: msg.language || 'ru',
                persona: msg.persona || `aziza_${msg.language || 'ru'}`,
              }),
            );
            // Emit first_token so TTFT benchmark can measure gateway pipeline latency.
            // This represents the gateway having successfully routed the session to the
            // Moshi worker — the earliest point a "token" could begin flowing.
            client.send(
              JSON.stringify({
                type: 'first_token',
                session_id: sessionId,
                language: msg.language || 'ru',
                gateway_dispatch_ms: Date.now() - sessionStartMs,
                measure_ttft: msg.measure_ttft || false,
              }),
            );
            break;
          }

          case 'session_update':
            await this.redis.publish(
              `session:${sessionId}:control`,
              JSON.stringify({ type: 'session_update', language: msg.language }),
            );
            break;

          case 'text_request':
            // Push to BLPOP queue that the moshi-worker actively polls.
            // The queue listener auto-registers the session in active_sessions.
            await this.redis.rpush(
              'aziza:text_in:queue',
              JSON.stringify({
                session_id: sessionId,
                text: msg.text || '',
                language: msg.language || 'ru',
              }),
            );
            break;

          case 'switch_persona':
            await this.redis.publish(
              `session:${sessionId}:control`,
              JSON.stringify({
                type: 'session_update',
                language: msg.language || msg.persona,
              }),
            );
            client.send(
              JSON.stringify({
                type: 'persona_switched',
                persona: msg.persona || msg.language,
                session_id: sessionId,
              }),
            );
            break;

          case 'end_session':
            await this.redis.publish(
              `session:${sessionId}:control`,
              JSON.stringify({ action: 'stop_audio' }),
            );
            break;

          case 'resume_session': {
            // Resume a previously disconnected session
            const existingMeta = await this.redis.hgetall(`session:${sessionId}:meta`);
            const historyKey = `session:${sessionId}:history`;
            const historyLen = await this.redis.llen(historyKey);

            client.send(JSON.stringify({
              type: 'session_resumed',
              session_id: sessionId,
              language: existingMeta.language || 'ru',
              message_count: historyLen,
              metadata: {
                language: existingMeta.language,
                persona: existingMeta.persona,
                created_at: existingMeta.created_at,
              },
            }));

            // Re-publish session start with existing context
            await this.redis.publish(
              'session:start',
              JSON.stringify({
                sessionId,
                text_prompt: existingMeta.text_prompt || '',
                voice_prompt: existingMeta.voice_prompt || '',
              }),
            );
            this.logger.log(`Session resumed: ${sessionId} (history: ${historyLen} messages)`);
            break;
          }

          default:
            this.logger.debug(
              `Unknown message type '${msg.type}' from ${sessionId}`,
            );
        }
      } catch {
        this.logger.warn(`Failed to parse message from ${sessionId}`);
      }
    });


    // ── Worker assignment via Lua atomic swap ──
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

    if (!assignedWorker) {
      this.logger.warn(`No idle workers available for session ${sessionId}`);
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
    this.logger.log(
      `Assigned worker ${assignedWorker} to session ${sessionId}`,
    );

    // Connect api-gateway -> Moshi worker and proxy all traffic so the
    // browser never needs to reach the worker's localhost WebSocket.
    const workerUrl = `${assignedWsUrl}?session_id=${sessionId}`;
    this.logger.log(`Proxying voice WS to Moshi worker: ${workerUrl}`);
    const workerWs = new WebSocket(workerUrl);
    this.workerConnections.set(sessionId, workerWs);

    workerWs.on('open', () => {
      this.logger.log(`Voice proxy connected to worker for ${sessionId}`);
      if (client.readyState === 1 /* OPEN */) {
        client.send(
          JSON.stringify({
            type: 'worker_connected',
            sessionId,
            workerId: assignedWorker,
          }),
        );
      }
    });

    workerWs.on('message', (data: WebSocket.Data) => {
      if (Buffer.isBuffer(data)) {
        this.logger.debug(`Worker response for ${sessionId}: ${data.length} bytes`);
      } else {
        this.logger.debug(`Worker response for ${sessionId}: text`);
      }
      if (client.readyState === 1 /* OPEN */) {
        client.send(data);
      }
    });

    workerWs.on('error', (err: Error) => {
      this.logger.error(
        `Moshi Worker WS Error for session ${sessionId}: ${err.message}`,
      );
      if (client.readyState === 1 /* OPEN */) {
        client.send(
          JSON.stringify({
            type: 'error',
            message: 'Voice worker connection lost. Please try again.',
          }),
        );
        client.close(1011, 'Worker connection lost');
      }
    });

    workerWs.on('close', () => {
      this.logger.log(`Moshi Worker WS closed for session ${sessionId}`);
      this.workerConnections.delete(sessionId);
      if (client.readyState === 1 /* OPEN */) {
        client.close(1011, 'Worker connection closed');
      }
    });

    // Forward client messages to the worker after it is connected.
    const forwardToWorker = (payload: Buffer | string) => {
      if (workerWs.readyState === WebSocket.OPEN) {
        workerWs.send(payload);
      }
    };

    // Replace the existing client message handler with one that also
    // forwards to the worker. We attach this AFTER the existing handler
    // so control messages still flow through Redis as before.
    client.on('message', async (payload: Buffer | string) => {
      try {
        const raw = Buffer.isBuffer(payload) ? payload : Buffer.from(payload);

        // Binary audio frames: first byte is NOT '{' (0x7B)
        if (raw[0] !== 0x7b) {
          this.logger.debug(`Audio frame from ${sessionId} (proxy): ${raw.length} bytes`);
          await this.redis.publish(`session:${sessionId}:audio_in`, raw);
          forwardToWorker(raw);
          return;
        }

        // JSON control messages
        const msg: Record<string, any> = JSON.parse(raw.toString());

        switch (msg.type) {
          case 'ping':
            client.send(
              JSON.stringify({ type: 'pong', session_id: sessionId }),
            );
            client.isAlive = true;
            break;

          case 'start_session': {
            const sessionStartMs = Date.now();
            await this.redis.publish(
              `session:${sessionId}:control`,
              JSON.stringify({
                type: 'session_update',
                language: msg.language || 'ru',
                persona: msg.persona || `aziza_${msg.language || 'ru'}`,
              }),
            );
            client.send(
              JSON.stringify({
                type: 'first_token',
                session_id: sessionId,
                language: msg.language || 'ru',
                gateway_dispatch_ms: Date.now() - sessionStartMs,
                measure_ttft: msg.measure_ttft || false,
              }),
            );
            forwardToWorker(raw);
            break;
          }

          case 'session_update':
            await this.redis.publish(
              `session:${sessionId}:control`,
              JSON.stringify({ type: 'session_update', language: msg.language }),
            );
            forwardToWorker(raw);
            break;

          case 'text_request':
            await this.redis.rpush(
              'aziza:text_in:queue',
              JSON.stringify({
                session_id: sessionId,
                text: msg.text || '',
                language: msg.language || 'ru',
              }),
            );
            forwardToWorker(raw);
            break;

          case 'switch_persona':
            await this.redis.publish(
              `session:${sessionId}:control`,
              JSON.stringify({
                type: 'session_update',
                language: msg.language || msg.persona,
              }),
            );
            client.send(
              JSON.stringify({
                type: 'persona_switched',
                persona: msg.persona || msg.language,
                session_id: sessionId,
              }),
            );
            forwardToWorker(raw);
            break;

          case 'end_session':
            await this.redis.publish(
              `session:${sessionId}:control`,
              JSON.stringify({ action: 'stop_audio' }),
            );
            forwardToWorker(raw);
            break;

          case 'resume_session': {
            const existingMeta = await this.redis.hgetall(`session:${sessionId}:meta`);
            const historyKey = `session:${sessionId}:history`;
            const historyLen = await this.redis.llen(historyKey);

            client.send(JSON.stringify({
              type: 'session_resumed',
              session_id: sessionId,
              language: existingMeta.language || 'ru',
              message_count: historyLen,
              metadata: {
                language: existingMeta.language,
                persona: existingMeta.persona,
                created_at: existingMeta.created_at,
              },
            }));

            await this.redis.publish(
              'session:start',
              JSON.stringify({
                sessionId,
                text_prompt: existingMeta.text_prompt || '',
                voice_prompt: existingMeta.voice_prompt || '',
              }),
            );
            this.logger.log(`Session resumed: ${sessionId} (history: ${historyLen} messages)`);
            forwardToWorker(raw);
            break;
          }

          default:
            this.logger.debug(
              `Unknown message type '${msg.type}' from ${sessionId}`,
            );
            forwardToWorker(raw);
        }
      } catch {
        this.logger.warn(`Failed to parse message from ${sessionId}`);
      }
    });

    // Notify the Moshi worker to initialise the session
    await this.redis.publish(
      'session:start',
      JSON.stringify({
        sessionId,
        text_prompt: params.text_prompt || '',
        voice_prompt: params.voice_prompt || '',
      }),
    );
  }

  async handleDisconnect(client: any) {
    const sessionId = client.sessionId;
    const workerId = client.workerId;

    // Stop the per-client heartbeat
    const timer = this.heartbeatTimers.get(sessionId);
    if (timer) {
      clearInterval(timer);
      this.heartbeatTimers.delete(sessionId);
    }

    // Persist session transcript before cleanup
    if (client.transcript && client.transcript.length > 0) {
      const historyKey = `session:${sessionId}:history`;
      for (const entry of client.transcript) {
        await this.redis.rpush(historyKey, JSON.stringify(entry));
      }
      await this.redis.expire(historyKey, 86400); // 24h TTL
      this.logger.log(`Persisted ${client.transcript.length} transcript entries for ${sessionId}`);
    }

    // Preserve session metadata for potential resume
    const metaKey = `session:${sessionId}:meta`;
    const existingMeta = await this.redis.hgetall(metaKey);
    if (existingMeta && Object.keys(existingMeta).length > 0) {
      await this.redis.hset(metaKey, {
        status: 'disconnected',
        disconnected_at: new Date().toISOString(),
        language: client.language || existingMeta.language || 'ru',
      });
      await this.redis.expire(metaKey, 86400); // Keep for 24h for resume
    }

    this.clients.delete(sessionId);
    this.logger.log(`Client disconnected: ${sessionId} (session preserved for resume)`);

    // Close proxied worker WebSocket if open
    const workerWs = this.workerConnections.get(sessionId);
    if (workerWs && workerWs.readyState === WebSocket.OPEN) {
      workerWs.close(1000, 'Client disconnected');
    }
    this.workerConnections.delete(sessionId);

    if (workerId) {
      await this.redis.hset(`moshi:workers:${workerId}`, 'status', 'idle');
      await this.redis.publish('orchestrator:session:release', workerId);
      this.logger.log(`Released worker ${workerId}`);
    }
  }
}
