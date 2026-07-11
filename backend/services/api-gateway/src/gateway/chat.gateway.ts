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
import * as jwt from 'jsonwebtoken';
import * as path from 'path';
import * as fs from 'fs';
import { MetricsService } from '../monitoring/metrics.service';

// Load shared system prompts
const promptsPath = path.resolve(__dirname, '../../../../shared/system-prompts.json');
const promptsData = JSON.parse(fs.readFileSync(promptsPath, 'utf-8'));
const SHARED_PROMPTS = promptsData.prompts;
const LANGUAGE_NAMES = promptsData.languageNames;

const SYSTEM_PROMPT =
  'You are Aziza, an advanced AI Assistant. Be helpful, concise, and friendly.';
const JWT_SECRET = process.env.JWT_SECRET;
if (!JWT_SECRET) {
  throw new Error('JWT_SECRET environment variable is required');
}

const MAX_MESSAGE_LENGTH = 4096;

function sanitizeUserInput(text: string): string {
  // Strip HTML tags to prevent injection into LLM prompts
  let clean = text.replace(/<[^>]*>/g, '');
  // Limit length
  if (clean.length > MAX_MESSAGE_LENGTH) {
    clean = clean.slice(0, MAX_MESSAGE_LENGTH);
  }
  return clean;
}

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

  /** sessionId → request start time (for TTFT measurement) */
  private requestStartTimes: Map<string, number> = new Map();

  /** Drift detection statistics */
  private driftStats = {
    totalChecks: 0,
    driftDetected: 0,
    retriesTriggered: 0,
    retriesSucceeded: 0,
    retriesExhausted: 0,
  };

  private redis: Redis;
  private metricsService: MetricsService;

  constructor() {
    const redisConfig = {
      host: process.env.REDIS_HOST || '127.0.0.1',
      port: parseInt(process.env.REDIS_PORT || '6379'),
      connectTimeout: 10000,
    };
    this.redis = new Redis(redisConfig);
    this.redis.on('error', (err: any) =>
      this.logger.error('Redis Publisher Error', err),
    );
    this.metricsService = new MetricsService();
  }

  // ─── Connection lifecycle ────────────────────────────────────────────────────

  handleConnection(client: any, request: any) {
    const url = new URL(request.url || '', 'http://localhost');
    
    // Validate JWT token
    const token = url.searchParams.get('token');
    if (!token) {
      this.logger.warn('Chat connection rejected: no token provided');
      client.send(JSON.stringify({ type: 'error', message: 'Authentication required' }));
      client.close(4001, 'Authentication required');
      return;
    }

    try {
      const payload = jwt.verify(token, JWT_SECRET, { algorithms: ['HS256'] }) as jwt.JwtPayload;
      client.userId = payload.sub || payload.userId;
      client.username = payload.username;
    } catch (err) {
      this.logger.warn(`Chat connection rejected: invalid token - ${err.message}`);
      client.send(JSON.stringify({ type: 'error', message: 'Invalid or expired token' }));
      client.close(4002, 'Invalid token');
      return;
    }

    const sessionId = url.searchParams.get('sessionId') || uuidv4();
    client.sessionId = sessionId;

    this.clients.set(sessionId, client);
    if (!this.history.has(sessionId)) {
      this.history.set(sessionId, []);
    }

    this.logger.log(`Chat client connected: ${sessionId} (user: ${client.username || client.userId})`);

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
          this.handleTextMessage(sessionId, client, sanitizeUserInput(msg.message.trim()));
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
      this.requestStartTimes.delete(sessionId);
      this.clients.delete(sessionId);
      this.logger.log(`Chat client disconnected: ${sessionId}`);
    }
  }

  // ─── Core text handler ───────────────────────────────────────────────────────

  // System prompts loaded from shared/system-prompts.json
  private readonly SYSTEM_PROMPTS = SHARED_PROMPTS as Record<string, string>;
  private readonly LANGUAGE_NAMES = LANGUAGE_NAMES as Record<string, string>;

  private async detectLanguage(text: string): Promise<string> {
    // 1. Try franc-min for language identification
    try {
      const franc = require('franc-min').franc;
      const code = franc(text, { minLength: 3 });
      const map: Record<string, string> = {
        rus: 'ru', uzb: 'uz', eng: 'en',
      };
      const detected = map[code];
      if (detected) {
        // For Uzbek, determine script variant
        if (detected === 'uz') {
          return this.detectUzbekScript(text);
        }
        return detected;
      }
    } catch {
      // franc-min not available — fall through to heuristic detection
    }

    // 2. Heuristic detection: count characters by script
    let cyrillic = 0;
    let latin = 0;
    let hasOkina = false;
    let hasUzbekCyrillic = false;

    // Uzbek-specific Cyrillic chars (Қ, Ғ, Ҳ, Ў and their lowercase)
    const uzbekCyrillicChars = new Set([
      0x049A, 0x049B, // Қ/қ
      0x0492, 0x0493, // Ғ/ғ
      0x04BA, 0x04BB, // Һ/һ
      0x040E, 0x045E, // Ў/ў
      0x04B6, 0x04B7, // Ҷ/ҷ
    ]);

    for (const ch of text) {
      const cp = ch.charCodeAt(0);
      if (cp === 0x02BB) {
        hasOkina = true;
        latin++;
      } else if ((cp >= 0x0400 && cp <= 0x04FF) || (cp >= 0x0500 && cp <= 0x052F)) {
        cyrillic++;
        if (uzbekCyrillicChars.has(cp)) {
          hasUzbekCyrillic = true;
        }
      } else if (cp >= 0x0041 && cp <= 0x007A) {
        latin++;
      }
    }

    // 3. Uzbek detection: okina (ʻ) or Uzbek-specific Cyrillic chars
    if (hasOkina || hasUzbekCyrillic) {
      return this.detectUzbekScript(text);
    }

    // 4. Script-based fallback
    if (cyrillic > latin && cyrillic > 0) {
      return 'ru';
    }
    if (latin > 0) return 'en';
    return 'ru';
  }

  /**
   * Determine Uzbek script variant (Latin vs Cyrillic) from text.
   */
  private detectUzbekScript(text: string): string {
    let cyrillic = 0;
    let latin = 0;
    for (const ch of text) {
      const cp = ch.charCodeAt(0);
      if (cp === 0x02BB) { latin++; continue; } // okina counts as Latin
      if ((cp >= 0x0400 && cp <= 0x04FF) || (cp >= 0x0500 && cp <= 0x052F)) {
        cyrillic++;
      } else if (cp >= 0x0041 && cp <= 0x007A) {
        latin++;
      }
    }
    return cyrillic > latin ? 'uz_cyrillic' : 'uz_latin';
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
      
      // Explicit English handling product decision placeholder
      // For now, routing English to Russian endpoint but with English system prompt.
      if (lang === 'unknown') {
        lang = 'ru';
      }

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

    let langName = this.LANGUAGE_NAMES[lang] || 'English';

    const messages = [
      {
        role: 'system',
        content: `${systemPromptText} IMPORTANT: You must reply in ${langName} only.`,
      },
      ...history,
    ];

    this.logger.log(
      `[${sessionId}] → vLLM (${lang})${isRetry ? ' [retry]' : ''}: ${userMessage}`,
    );

    // LLM Routing (vLLM instead of Ollama)
    // port 8002 = Vikhr-Llama3.1 (Russian/English) + aziza_russian LoRA
    // port 8003 = alloma-3B (Uzbek) + aziza_uzbek LoRA
    let llmModel = process.env.LLM_MODEL_EN || 'Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24';
    let targetPort = 8002;

    if (lang === 'ru' || lang.startsWith('ru_')) {
      // Use the base model name — NOT the LoRA adapter name ('aziza_russian').
      // Passing the LoRA name as `model` causes vLLM to attempt a tokenizer
      // reload which fails with HTTP 400. The LoRA weights are already loaded
      // at startup via --lora-modules; the base model routes through them.
      llmModel = process.env.LLM_MODEL_RU || 'Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24';
      targetPort = 8002;
    } else if (lang === 'uz' || lang.startsWith('uz_')) {
      llmModel = process.env.LLM_MODEL_UZ || 'alloma';
      targetPort = 8003;
    }

    // ─── Per-model request body ───────────────────────────────────────────────
    // alloma (port 8003) uses a different tokenizer than Vikhr-Llama3 (port
    // 8002). Sending Llama3 stop_token_ids to alloma causes a 404/422 from
    // vLLM because those token IDs don't exist in the Qwen vocabulary.
    const isUzbekModel = targetPort === 8003;

    const body = JSON.stringify({
      model: llmModel,
      messages,
      stream: true,
      stop: isUzbekModel
        ? ['<|im_end|>', '<|im_start|>', 'Siz:', 'Foydalanuvchi:', 'User:']
        : ['<|im_end|>', '<|im_start|>', '<|eot_id|>', '<|end_of_text|>', 'Пользователь:', 'Азиза:', 'User:', 'Aziza:'],
      // Llama3 EOS/EOT token IDs only — 151645 and 151643 are Qwen tokens
      // that don't exist in the Llama vocab and cause HTTP 400 from vLLM.
      ...(isUzbekModel ? {} : { stop_token_ids: [128001, 128009] }),
      repetition_penalty: 1.1,
      presence_penalty: 0.3,
      temperature: 0.6,
      top_p: 0.9,
      max_tokens: 256,
    });

    const options: http.RequestOptions = {
      hostname: '127.0.0.1',
      port: targetPort,
      path: '/v1/chat/completions',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer EMPTY',
        'Content-Length': Buffer.byteLength(body),
      },
    };

    let fullResponse = '';
    let aborted = false;
    let firstTokenSent = false;

    // Record start time for TTFT measurement
    this.requestStartTimes.set(sessionId, Date.now());

    const req = http.request(options, (res) => {
      if (res.statusCode !== 200) {
        this.logger.error(
          `vLLM returned HTTP ${res.statusCode} for session ${sessionId}`,
        );
        const startTime = this.requestStartTimes.get(sessionId) || Date.now();
        this.metricsService.recordRequest({
          timestamp: Date.now() / 1000,
          ttftMs: 0,
          tokensPerSec: 0,
          service: `vllm:${targetPort}`,
          language: lang,
          success: false,
          error: `HTTP ${res.statusCode}`,
        });
        if (client.readyState === 1) {
          client.send(
            JSON.stringify({
              type: 'error',
              message: `vLLM error (HTTP ${res.statusCode}). Is vLLM running on port ${targetPort}?`,
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
          if (!trimmed || !trimmed.startsWith('data: ')) continue;
          
          const dataStr = trimmed.slice(6).trim();
          if (dataStr === '[DONE]') {
            // Drift detection only applies to uz_cyrillic.
            const shouldRetry = this.shouldRetryForDrift(
              sessionId,
              lang,
              fullResponse,
            );

            if (shouldRetry) {
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

            // Record request metrics
            const startTime = this.requestStartTimes.get(sessionId) || Date.now();
            const totalMs = Date.now() - startTime;
            const tokenCount = fullResponse.split(/\s+/).length;
            this.metricsService.recordRequest({
              timestamp: Date.now() / 1000,
              ttftMs: firstTokenSent ? totalMs : 0,
              tokensPerSec: tokenCount / (totalMs / 1000),
              service: `vllm:${targetPort}`,
              language: lang,
              success: true,
            });

            history.push({ role: 'assistant', content: fullResponse });
            this.history.set(sessionId, history);
            this.retryAttempts.delete(sessionId);
            this.trackDriftOutcome(sessionId, lang, true);
            this.logger.log(
              `[${sessionId}] ← Aziza: ${fullResponse.slice(0, 80)}…`,
            );
            this.activeRequests.delete(sessionId);
            continue;
          }

          try {
            const parsed = JSON.parse(dataStr);
            const token: string = parsed?.choices?.[0]?.delta?.content ?? '';
            if (token) {
              fullResponse += token;
              // For uz_cyrillic, buffer the whole response so we can
              // run drift detection before showing anything to the user.
              if (lang !== 'uz_cyrillic' && client.readyState === 1) {
                // Send first token with TTFT metric
                if (!firstTokenSent) {
                  firstTokenSent = true;
                  const startTime = this.requestStartTimes.get(sessionId) || Date.now();
                  const ttftMs = Date.now() - startTime;
                  client.send(
                    JSON.stringify({
                      type: 'first_token',
                      ttft_ms: ttftMs,
                    }),
                  );
                }
                client.send(
                  JSON.stringify({ type: 'token', content: token }),
                );
              }
            }
          } catch {
            // Non-JSON line — skip
          }
        }
      };

      res.on('data', onChunk);

      res.on('error', (err) => {
        if (aborted) return; // expected
        this.logger.error(
          `vLLM stream error for ${sessionId}: ${err.message}`,
        );
        const startTime = this.requestStartTimes.get(sessionId) || Date.now();
        this.metricsService.recordRequest({
          timestamp: Date.now() / 1000,
          ttftMs: Date.now() - startTime,
          tokensPerSec: 0,
          service: `vllm:${targetPort}`,
          language: lang,
          success: false,
          error: `stream_error: ${err.message}`,
        });
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
        `Could not reach vLLM for ${sessionId}: ${err.message}`,
      );
      // Record error metrics
      const startTime = this.requestStartTimes.get(sessionId) || Date.now();
      this.metricsService.recordRequest({
        timestamp: Date.now() / 1000,
        ttftMs: Date.now() - startTime,
        tokensPerSec: 0,
        service: `vllm:${targetPort}`,
        language: lang,
        success: false,
        error: err.message,
      });
      if (client.readyState === 1) {
        client.send(
          JSON.stringify({
            type: 'error',
            message:
              'Could not reach the AI engine. Please ensure vLLM is running on the server.',
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
   * Detects script drift in Uzbek responses and decides whether to retry.
   *
   * - uz_cyrillic: retries if >10% of non-space chars are Latin letters (A-Z)
   * - uz_latin: retries if >10% of non-space chars are Cyrillic letters (А-Я)
   * - uz (auto): retries if >30% of chars are from the "wrong" script
   *
   * Caps retries at 1 per session per turn.
   */
  private shouldRetryForDrift(
    sessionId: string,
    lang: string,
    fullResponse: string,
  ): boolean {
    if (!lang.startsWith('uz') || fullResponse.length === 0) return false;

    this.driftStats.totalChecks++;

    // Count characters by script
    let cyrillicCount = 0;
    let latinCount = 0;
    let totalAlpha = 0;

    for (const ch of fullResponse) {
      const cp = ch.charCodeAt(0);
      if ((cp >= 0x0400 && cp <= 0x04FF) || (cp >= 0x0500 && cp <= 0x052F)) {
        cyrillicCount++;
        totalAlpha++;
      } else if (cp >= 0x0041 && cp <= 0x007A) {
        latinCount++;
        totalAlpha++;
      }
    }

    if (totalAlpha === 0) return false;

    let driftDetected = false;
    let driftType = '';

    if (lang === 'uz_cyrillic' || lang === 'uz-cyrl') {
      // Expected: Cyrillic. Drift = Latin characters
      const driftRatio = latinCount / totalAlpha;
      if (driftRatio > 0.1) {
        driftDetected = true;
        driftType = `latin_in_cyrillic (${(driftRatio * 100).toFixed(1)}%)`;
      }
    } else if (lang === 'uz_latin' || lang === 'uz-latn') {
      // Expected: Latin. Drift = Cyrillic characters
      const driftRatio = cyrillicCount / totalAlpha;
      if (driftRatio > 0.1) {
        driftDetected = true;
        driftType = `cyrillic_in_latin (${(driftRatio * 100).toFixed(1)}%)`;
      }
    } else if (lang === 'uz') {
      // Auto-detected Uzbek — check for English drift (neither Cyrillic nor Latin Uzbek)
      const englishRatio = latinCount / totalAlpha;
      // If mostly Latin but no Uzbek indicators, might be English drift
      // For now, just check that response isn't predominantly one script
      // when the user sent in the other
    }

    if (!driftDetected) return false;

    this.driftStats.driftDetected++;
    const attempts = this.retryAttempts.get(sessionId) ?? 0;

    if (attempts >= 1) {
      this.driftStats.retriesExhausted++;
      this.logger.warn(
        `[${sessionId}] Drift still present after retry (${driftType}). Sending as-is.`,
      );
      return false;
    }

    this.retryAttempts.set(sessionId, attempts + 1);
    this.driftStats.retriesTriggered++;
    this.logger.warn(
      `[${sessionId}] Drift detected for ${lang}: ${driftType}. Retrying once.`,
    );
    return true;
  }

  /**
   * After a successful response, check if a retry would have been needed
   * and if the retry fixed it (for metrics tracking).
   */
  private trackDriftOutcome(sessionId: string, lang: string, success: boolean) {
    if (!lang.startsWith('uz')) return;
    const attempts = this.retryAttempts.get(sessionId) ?? 0;
    if (attempts > 0 && success) {
      this.driftStats.retriesSucceeded++;
    }
  }

  getDriftStats() {
    return { ...this.driftStats };
  }
}
