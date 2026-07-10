import {
  WebSocketGateway,
  WebSocketServer,
  OnGatewayConnection,
  OnGatewayDisconnect,
} from '@nestjs/websockets';
import { Server } from 'ws';
import { Logger } from '@nestjs/common';
import { v4 as uuidv4 } from 'uuid';
import * as http from 'http';
import Redis from 'ioredis';

const OLLAMA_HOST = process.env.OLLAMA_HOST || '127.0.0.1';
const OLLAMA_PORT = parseInt(process.env.OLLAMA_PORT || '11434');
const OLLAMA_MODEL = process.env.OLLAMA_MODEL || 'llama3';

const SYSTEM_PROMPT =
  'You are Aziza, an advanced AI Assistant. Be helpful, concise, and friendly.';

/**
 * FIXED ChatGateway
 *
 * Bugs fixed vs. the original:
 *
 * 1. Retry-logic fall-through: the old code did `return;` inside the
 *    `for (const line of lines)` callback. That `return` only exits the
 *    arrow function passed to `res.on('data', ...)`, so execution still
 *    fell through to send `{ type: 'done' }` and pushed the drifted
 *    assistant reply into history. We now track retries explicitly and
 *    bail out of the chunk handler entirely on retry.
 *
 * 2. Duplicated user message on retry: the old recursive call re-entered
 *    `handleTextMessage`, which pushed `{ role: 'user' }` into history
 *    a second time. We now pass an `isRetry` flag and skip the push.
 *
 * 3. Race between two concurrent Ollama requests: when a retry fired,
 *    both the original and the retry HTTP requests were still attached
 *    to the same client and could both call `client.send(...)`. We now
 *    abort the original request via `req.destroy()` before retrying.
 *
 * 4. The retry flag lived on `(client as any).hasRetried`, which leaks
 *    state across sessions on the same WebSocket and is never reset on
 *    disconnect. We moved it to a per-sessionId Map that is cleared on
 *    disconnect and after a successful response.
 */
@WebSocketGateway({
  path: '/api/chat-text',
  cors: { origin: '*' },
})
export class ChatGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;

  private readonly logger = new Logger(ChatGateway.name);

  /** sessionId → WebSocket client */
  private clients: Map<string, any> = new Map();

  /** sessionId → conversation history [ { role, content } ] */
  private history: Map<string, Array<{ role: string; content: string }>> =
    new Map();

  /** sessionId → in-flight HTTP request to Ollama (so we can cancel it) */
  private activeRequests: Map<string, http.ClientRequest> = new Map();

  /** sessionId → number of drift retries already attempted (cap = 1) */
  private retryAttempts: Map<string, number> = new Map();

  private redis: Redis;

  constructor() {
    const redisConfig = {
      host: process.env.REDIS_HOST || '127.0.0.1',
      port: parseInt(process.env.REDIS_PORT || '6379'),
      connectTimeout: 10000,
    };
    this.redis = new Redis(redisConfig);
    this.redis.on('error', (err) =>
      this.logger.error('Redis Publisher Error', err),
    );
  }

  // ─── Connection lifecycle ────────────────────────────────────────────────────

  handleConnection(client: any, request: any) {
    const url = new URL(request.url || '', 'http://localhost');
    const sessionId = url.searchParams.get('sessionId') || uuidv4();
    client.sessionId = sessionId;

    this.clients.set(sessionId, client);
    if (!this.history.has(sessionId)) {
      this.history.set(sessionId, []);
    }

    this.logger.log(`Chat client connected: ${sessionId}`);

    if (client.readyState === 1) {
      client.send(JSON.stringify({ type: 'ready' }));
    }

    client.on('message', (payload: any) => {
      try {
        const msg = JSON.parse(payload.toString());
        if (msg.type === 'ping') {
          client.send(JSON.stringify({ type: 'pong' }));
        } else if (msg.type === 'session_update') {
          this.redis.publish(
            `session:${sessionId}:control`,
            JSON.stringify({
              type: 'session_update',
              language: msg.language,
            }),
          );
          client.language = msg.language;
          this.logger.log(
            `Session ${sessionId} updated language to ${msg.language}`,
          );
        } else if (msg.message) {
          if (msg.language) {
            client.language = msg.language;
          }
          this.handleTextMessage(sessionId, client, msg.message.trim());
        }
      } catch {
        this.logger.warn(`Failed to parse message from ${sessionId}`);
      }
    });
  }

  handleDisconnect(client: any) {
    const sessionId = client.sessionId;
    if (sessionId) {
      // Cancel any in-flight Ollama request and clear per-session state.
      this.activeRequests.get(sessionId)?.destroy();
      this.activeRequests.delete(sessionId);
      this.retryAttempts.delete(sessionId);
      this.clients.delete(sessionId);
      this.logger.log(`Chat client disconnected: ${sessionId}`);
    }
  }

  // ─── Core text handler ───────────────────────────────────────────────────────

  private readonly SYSTEM_PROMPTS = {
    en: 'You are Aziza — a warm, intelligent, and attentive AI assistant. Speak naturally and conversationally. Keep responses concise. RESPOND ONLY IN ENGLISH.',
    ru: 'Ты Азиза — тёплый, умный и внимательный AI-ассистент. Говори естественно по-русски, как живой человек. Избегай формальных оборотов. Отвечай кратко и по делу. ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.',
    ru_colloquial: 'Ты Азиза — тёплый, умный и внимательный AI-ассистент. Говори естественно и непринужденно по-русски, используй разговорный стиль. ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.',
    ru_professional: 'Вы Азиза — профессиональный, умный и внимательный AI-ассистент. Отвечайте вежливо, используя деловой и профессиональный стиль русского языка. ОТВЕЧАЙТЕ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.',
    uz: "Siz Aziza — mehribon, aqlli va diqqatli AI yordamchisiz. O'zbek tilida tabiiy va jonli gapiring. Qisqa va aniq javob bering. FAQAT O'ZBEK TILIDA JAVOB BERING.",
    uz_latin: "Siz Aziza — mehribon, aqlli va diqqatli AI yordamchisiz. Iltimos, rasmiy 'Siz' yoki norasmiy 'sen' shakllarini vaziyatga qarab ishlating. FAQAT O'ZBEK LOTIN YOZUVIDA JAVOB BERING.",
    uz_cyrillic: 'Сиз Азиза — меҳрибон, ақлли ва диққатли АИ ёрдамчисиз. Илтимос, расмий \'Сиз\' ёки норасмий \'сен\' шаклларини вазиятга қараб ишлатинг. ФАҚАТ ЎЗБЕК КИРИЛЛ ЁЗУВИДА ЖАВОБ БЕРИНГ.',
  } as const;

  private async detectLanguage(text: string): Promise<string> {
    try {
      const res = await fetch('http://127.0.0.1:8000/lang/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (res.ok) {
        const data = await res.json();
        return data.language || 'en';
      }
    } catch (err) {
      this.logger.error(`Language detection failed: ${err}`);
    }
    return 'ru';
  }

  /**
   * @param isRetry  true when called from a drift retry — skip pushing
   *                 the user message into history again.
   */
  private async handleTextMessage(
    sessionId: string,
    client: any,
    userMessage: string,
    isRetry: boolean = false,
  ) {
    let lang = client.language;
    if (!lang || lang === 'auto') {
      lang = await this.detectLanguage(userMessage);
      client.language = lang;
      this.redis.publish(
        `session:${sessionId}:control`,
        JSON.stringify({ type: 'session_update', language: lang }),
      );
    }

    const history = this.history.get(sessionId) ?? [];

    // Only push the user message on the first attempt — otherwise the
    // retry would duplicate the turn.
    if (!isRetry) {
      history.push({ role: 'user', content: userMessage });
      this.history.set(sessionId, history);
    }

    const systemPromptText =
      this.SYSTEM_PROMPTS[lang as keyof typeof this.SYSTEM_PROMPTS] ||
      this.SYSTEM_PROMPTS.en;

    let langName = 'English';
    if (lang === 'ru' || lang.startsWith('ru_')) langName = 'Russian';
    if (lang === 'uz' || lang.startsWith('uz_')) langName = 'Uzbek';

    const messages = [
      {
        role: 'system',
        content: `${systemPromptText} IMPORTANT: You must reply in ${langName} only.`,
      },
      ...history,
    ];

    this.logger.log(
      `[${sessionId}] → Ollama (${lang})${isRetry ? ' [retry]' : ''}: ${userMessage}`,
    );

    // LLM Routing
    let llmModel = process.env.LLM_MODEL_EN || 'qwen:latest';
    if (lang === 'uz' || lang.startsWith('uz_')) {
      llmModel = process.env.LLM_MODEL_UZ || 'qwen:latest';
    }

    const body = JSON.stringify({
      model: llmModel,
      messages,
      stream: true,
    });

    const options: http.RequestOptions = {
      hostname: OLLAMA_HOST,
      port: OLLAMA_PORT,
      path: '/api/chat',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
      },
    };

    let fullResponse = '';
    let aborted = false;

    const req = http.request(options, (res) => {
      if (res.statusCode !== 200) {
        this.logger.error(
          `Ollama returned HTTP ${res.statusCode} for session ${sessionId}`,
        );
        if (client.readyState === 1) {
          client.send(
            JSON.stringify({
              type: 'error',
              message: `Ollama error (HTTP ${res.statusCode}). Is Ollama running?`,
            }),
          );
        }
        this.activeRequests.delete(sessionId);
        return;
      }

      let buffer = '';

      const onChunk = (chunk: Buffer) => {
        if (aborted) {
          res.destroy();
          return;
        }

        buffer += chunk.toString('utf-8');
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          try {
            const parsed = JSON.parse(trimmed);
            const token: string = parsed?.message?.content ?? '';
            if (token) {
              fullResponse += token;
              // For uz_cyrillic, buffer the whole response so we can
              // run drift detection before showing anything to the
              // user. All other languages stream tokens immediately.
              if (lang !== 'uz_cyrillic' && client.readyState === 1) {
                client.send(
                  JSON.stringify({ type: 'token', content: token }),
                );
              }
            }

            if (parsed?.done) {
              // Drift detection only applies to uz_cyrillic.
              const shouldRetry = this.shouldRetryForDrift(
                sessionId,
                lang,
                fullResponse,
              );

              if (shouldRetry) {
                // Cancel the current request and re-enter without
                // pushing user message again. We must `return` from
                // the chunk handler immediately so the fall-through
                // code does not send `{ type: 'done' }` or push the
                // drifted reply into history.
                aborted = true;
                res.destroy();
                this.activeRequests.delete(sessionId);
                this.handleTextMessage(sessionId, client, userMessage, true);
                return;
              }

              // Flush buffered uz_cyrillic tokens if we didn't retry.
              if (
                lang === 'uz_cyrillic' &&
                fullResponse.length > 0 &&
                client.readyState === 1
              ) {
                client.send(
                  JSON.stringify({
                    type: 'token',
                    content: fullResponse,
                  }),
                );
              }

              if (client.readyState === 1) {
                client.send(JSON.stringify({ type: 'done' }));
              }

              history.push({ role: 'assistant', content: fullResponse });
              this.history.set(sessionId, history);
              this.retryAttempts.delete(sessionId);
              this.logger.log(
                `[${sessionId}] ← Aziza: ${fullResponse.slice(0, 80)}…`,
              );
              this.activeRequests.delete(sessionId);
            }
          } catch {
            // Non-JSON line — skip
          }
        }
      };

      res.on('data', onChunk);

      res.on('error', (err) => {
        if (aborted) return; // expected — we triggered this ourselves
        this.logger.error(
          `Ollama stream error for ${sessionId}: ${err.message}`,
        );
        if (client.readyState === 1) {
          client.send(
            JSON.stringify({
              type: 'error',
              message: 'Stream error from AI engine.',
            }),
          );
        }
        this.activeRequests.delete(sessionId);
      });
    });

    req.on('error', (err) => {
      if (aborted) return;
      this.logger.error(
        `Could not reach Ollama for ${sessionId}: ${err.message}`,
      );
      if (client.readyState === 1) {
        client.send(
          JSON.stringify({
            type: 'error',
            message:
              'Could not reach the AI engine. Please ensure Ollama is running on the server.',
          }),
        );
      }
      this.activeRequests.delete(sessionId);
    });

    // Track the in-flight request so disconnect / retry can cancel it.
    this.activeRequests.set(sessionId, req);

    req.write(body);
    req.end();
  }

  /**
   * Returns true iff we should retry the request because the
   * uz_cyrillic response drifted into Latin/ASCII characters.
   * Caps retries at 1 per session per turn.
   */
  private shouldRetryForDrift(
    sessionId: string,
    lang: string,
    fullResponse: string,
  ): boolean {
    if (lang !== 'uz_cyrillic') return false;
    if (fullResponse.length === 0) return false;

    let asciiCount = 0;
    for (const char of fullResponse) {
      const code = char.charCodeAt(0);
      if (
        code >= 32 &&
        code <= 126 &&
        !/\d/.test(char) &&
        !/[.,!?()\[\]{}"':;\s]/.test(char)
      ) {
        asciiCount++;
      }
    }

    const driftRatio = asciiCount / fullResponse.length;
    if (driftRatio <= 0.1) return false;

    const attempts = this.retryAttempts.get(sessionId) ?? 0;
    if (attempts >= 1) {
      this.logger.warn(
        `[${sessionId}] English drift still present after retry (ratio=${driftRatio.toFixed(2)}). Sending as-is.`,
      );
      return false;
    }

    this.retryAttempts.set(sessionId, attempts + 1);
    this.logger.warn(
      `[${sessionId}] English drift detected (ratio=${driftRatio.toFixed(2)}). Retrying once.`,
    );
    return true;
  }
}
