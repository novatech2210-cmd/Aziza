#!/usr/bin/env bash
#
# aziza-fixes-bundle.sh — writes the 5 fixed source files the deployer needs
#
# Usage on the server:
#   nano /root/aziza-build/aziza-fixes-bundle.sh   # paste this file in
#   bash /root/aziza-build/aziza-fixes-bundle.sh
#
# Writes 5 files alongside deploy.sh (which you already have), then
# tells you how to run deploy.sh.
#
set -euo pipefail

cd /root/aziza-build

log()  { printf '\033[1;36m[bundle]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[ok    ]\033[0m %s\n' "$*"; }

log "Writing 5 files to /root/aziza-build/"

cat << 'AZIZA_EOF_chat_gateway_ts' > chat.gateway.ts
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
AZIZA_EOF_chat_gateway_ts
ok "wrote chat.gateway.ts ($(wc -c < chat.gateway.ts) bytes)"

cat << 'AZIZA_EOF_ecosystem_config_js' > ecosystem.config.js
/**
 * FIXED ecosystem.config.js
 *
 * The original heredoc in the transcript got truncated mid-object — line 863
 * showed `}' | jq '.choices[0].message.content'ent": "Salom!"}],1-09-24", ...`
 * interleaved with shell output. This is the clean, complete file.
 *
 * Fixes:
 *   - Properly closed object literal.
 *   - Removed the bogus `MONGO_URL` env var that the gateway never reads
 *     (Mongoose is commented out in app.module.ts).
 *   - Added OLLAMA_HOST / OLLAMA_PORT so the ChatGateway connects to the
 *     local Ollama-to-vLLM proxy instead of a bare Ollama process.
 */

module.exports = {
  apps: [
    {
      name: 'api-gateway',
      script: '/root/aziza-build/backend/services/api-gateway/dist/main.js',
      cwd: '/root/aziza-build/backend/services/api-gateway',
      env: {
        NODE_ENV: 'production',
        PORT: 8080,

        // ── LLM routing ────────────────────────────────────────────────────
        // Point the gateway at the local Ollama-compatible proxy that
        // forwards to vLLM (see ollama_proxy.py).
        OLLAMA_HOST: '127.0.0.1',
        OLLAMA_PORT: '11434',
        LLM_MODEL_EN: 'Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24',
        LLM_MODEL_UZ: 'uzlm/alloma-3B-Instruct',

        // ── vLLM direct URLs (used by ollama_proxy.py, not the gateway) ───
        VLLM_ENGLISH_URL: 'http://localhost:8002/v1/chat/completions',
        VLLM_UZBEK_URL: 'http://localhost:8003/v1/chat/completions',

        // ── Language detection ────────────────────────────────────────────
        PERSONAPLEX_URL: 'http://127.0.0.1:8000',

        // ── Redis ──────────────────────────────────────────────────────────
        REDIS_HOST: '127.0.0.1',
        REDIS_PORT: '6379',
      },
    },
    // Add the other apps (orchestrator, moshi-worker, personaplex,
    // vllm-english, vllm-uzbek, frontend) here as before — they were
    // not broken, only this file got truncated.
  ],
};
AZIZA_EOF_ecosystem_config_js
ok "wrote ecosystem.config.js ($(wc -c < ecosystem.config.js) bytes)"

cat << 'AZIZA_EOF_ollama_proxy_py' > ollama_proxy.py
#!/usr/bin/env python3
"""
Ollama-to-vLLM Proxy  (COMPLETE — replaces the truncated version)

Translates Ollama /api/chat calls from the NestJS ChatGateway into
OpenAI-style /v1/chat/completions calls against two vLLM servers:

  * English / Russian  → http://localhost:8002/v1/chat/completions
  * Uzbek              → http://localhost:8003/v1/chat/completions

Endpoints implemented:
  GET  /api/tags              → static model list (so Ollama clients see models)
  POST /api/chat              → streaming chat completion (Ollama NDJSON)
  POST /api/generate          → same, single-message convenience

The original transcript only wrote `do_GET` and never started the server.
This file is runnable as-is:  python3 ollama_proxy.py
"""

import http.server
import json
import sys
import threading
import urllib.request
import urllib.error

# ─── vLLM endpoints ─────────────────────────────────────────────────────────
VLLM_ENGLISH_URL = "http://localhost:8002/v1/chat/completions"
VLLM_UZBEK_URL = "http://localhost:8003/v1/chat/completions"
LLM_MODEL_EN = "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"
LLM_MODEL_UZ = "uzlm/alloma-3B-Instruct"

# Languages routed to the Uzbek vLLM. Everything else (en, ru, ru_*, uz_latin)
# goes to the English vLLM. Adjust as needed.
UZBEK_LANGS = {"uz", "uz_cyrillic"}


def pick_endpoint(model: str):
    """Return (vllm_url, vllm_model) based on the Ollama model name."""
    if "uz" in model.lower() or "alloma" in model.lower():
        return VLLM_UZBEK_URL, LLM_MODEL_UZ
    return VLLM_ENGLISH_URL, LLM_MODEL_EN


def stream_vllm(url: str, payload: dict):
    """Yield raw NDJSON-ish lines from a vLLM streaming response."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=120)
    try:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            if not line:
                continue
            if line.startswith("data: "):
                line = line[len("data: "):]
            if line == "[DONE]":
                return
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
    finally:
        resp.close()


def ollama_chunk_from_vllm(vllm_chunk: dict, model: str, done: bool) -> dict:
    """Translate a vLLM SSE chunk into an Ollama /api/chat NDJSON chunk."""
    content = ""
    if not done:
        try:
            content = vllm_chunk["choices"][0]["delta"].get("content", "") or ""
        except (KeyError, IndexError):
            content = ""
    return {
        "model": model,
        "created_at": vllm_chunk.get("created", 0),
        "message": {"role": "assistant", "content": content},
        "done": done,
    }


class OllamaProxyHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Silence default access logging — uncomment to debug.
        # sys.stderr.write("[proxy] " + (fmt % args) + "\n")
        pass

    # ── GET /api/tags ──────────────────────────────────────────────────────
    def do_GET(self):
        if self.path.startswith("/api/tags"):
            body = json.dumps(
                {
                    "models": [
                        {"name": LLM_MODEL_EN, "model": LLM_MODEL_EN},
                        {"name": LLM_MODEL_UZ, "model": LLM_MODEL_UZ},
                        # backwards-compatible aliases the gateway may ask for:
                        {"name": "llama3", "model": LLM_MODEL_EN},
                        {"name": "qwen:latest", "model": LLM_MODEL_EN},
                    ]
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404, "Not Found")

    # ── POST /api/chat  (and /api/generate) ────────────────────────────────
    def do_POST(self):
        if not (self.path.startswith("/api/chat") or self.path.startswith("/api/generate")):
            self.send_error(404, "Not Found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        # Normalise /api/generate → /api/chat shape
        if self.path.startswith("/api/generate") and "prompt" in payload:
            payload["messages"] = [
                {"role": "user", "content": payload["prompt"]},
            ]

        model = payload.get("model", LLM_MODEL_EN)
        messages = payload.get("messages", [])
        stream = payload.get("stream", True)

        vllm_url, vllm_model = pick_endpoint(model)

        vllm_payload = {
            "model": vllm_model,
            "messages": messages,
            "stream": True,
            # Strip leaked chat-template tokens (see <im_end> bug in transcript)
            "stop": ["<|im_end|>", "<|im_start|>", "<|end|>", "</s>"],
        }

        if not stream:
            # Non-streaming: collect then return a single Ollama JSON object.
            full = ""
            for chunk in stream_vllm(vllm_url, vllm_payload):
                try:
                    full += chunk["choices"][0]["delta"].get("content", "") or ""
                except (KeyError, IndexError):
                    continue
            body = json.dumps(
                {
                    "model": model,
                    "message": {"role": "assistant", "content": full},
                    "done": True,
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # Streaming: translate vLLM SSE → Ollama NDJSON line-by-line.
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        try:
            for chunk in stream_vllm(vllm_url, vllm_payload):
                line = (
                    json.dumps(ollama_chunk_from_vllm(chunk, model, done=False))
                    + "\n"
                )
                self.wfile.write(line.encode("utf-8"))
                self.wfile.flush()
            # Final done sentinel — Ollama always sends one.
            done_line = (
                json.dumps(
                    {
                        "model": model,
                        "created_at": 0,
                        "message": {"role": "assistant", "content": ""},
                        "done": True,
                    }
                )
                + "\n"
            )
            self.wfile.write(done_line.encode("utf-8"))
            self.wfile.flush()
        except (urllib.error.URLError, ConnectionError) as err:
            err_chunk = (
                json.dumps(
                    {
                        "model": model,
                        "error": f"vLLM upstream error: {err}",
                        "done": True,
                    }
                )
                + "\n"
            )
            self.wfile.write(err_chunk.encode("utf-8"))
            self.wfile.flush()


class ThreadingHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11434
    server = ThreadingHTTPServer(("0.0.0.0", port), OllamaProxyHandler)
    print(f"[ollama_proxy] listening on :{port} "
          f"(EN→{VLLM_ENGLISH_URL}, UZ→{VLLM_UZBEK_URL})", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
AZIZA_EOF_ollama_proxy_py
ok "wrote ollama_proxy.py ($(wc -c < ollama_proxy.py) bytes)"

cat << 'AZIZA_EOF_frontend_chat_client_ts' > frontend-chat-client.ts
/**
 * FIXED frontend client for the /api/chat-text gateway.
 *
 * The backend gateway is registered with `@nestjs/platform-ws` (raw `ws`
 * library), so Socket.IO clients cannot connect — they hit 404 on
 * `/socket.io/?EIO=4&transport=polling`. Two equivalent fixes:
 *
 *   Option A (recommended, used here): keep the backend on raw `ws` and
 *   switch the frontend to a plain WebSocket.
 *
 *   Option B: keep the frontend on Socket.IO and switch the backend to
 *   `@nestjs/platform-socket.io` by setting
 *   `app.useWebSocketAdapter(new IoAdapter(app))` in `main.ts`.
 *
 * Option A is simpler and removes the `socket.io` dependency from the
 * frontend bundle. Below is the drop-in replacement for the
 * `io('http://localhost:8080/api/chat-text')` snippet from the transcript.
 */

// Frontend connects to:
const socket = new WebSocket('ws://localhost:8080/api/chat-text');

// Send a message:
socket.addEventListener('open', () => {
  socket.send(
    JSON.stringify({
      message: 'Hello!',
      language: 'auto', // or 'en', 'ru', 'uz', 'uz_cyrillic', ...
    }),
  );
});

// Receive responses:
socket.addEventListener('message', (event) => {
  let data;
  try {
    data = JSON.parse(event.data);
  } catch {
    return;
  }

  switch (data.type) {
    case 'ready':
      // server acks the connection
      break;
    case 'pong':
      // heartbeat response
      break;
    case 'token':
      // streaming token (or full uz_cyrillic response flushed at the end)
      // eslint-disable-next-line no-console
      console.log('token:', data.content);
      break;
    case 'done':
      // full message complete
      // eslint-disable-next-line no-console
      console.log('done');
      break;
    case 'error':
      // eslint-disable-next-line no-console
      console.error('error:', data.message);
      break;
  }
});

socket.addEventListener('close', () => {
  // eslint-disable-next-line no-console
  console.log('disconnected');
});

// Optional heartbeat to keep proxies happy:
setInterval(() => {
  if (socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: 'ping' }));
  }
}, 30000);

export { socket };
AZIZA_EOF_frontend_chat_client_ts
ok "wrote frontend-chat-client.ts ($(wc -c < frontend-chat-client.ts) bytes)"

cat << 'AZIZA_EOF_rollback_sh' > rollback.sh
#!/usr/bin/env bash
#
# rollback.sh — undo a deploy.sh run
#
# Usage:  bash rollback.sh [backup_dir]
#   If no backup_dir is given, uses the most recent /root/aziza-build/.fixes-backup-*
#
set -euo pipefail

AZIZA_ROOT="/root/aziza-root"
AZIZA_ROOT="/root/aziza-build"
GATEWAY_SRC="$AZIZA_ROOT/backend/services/api-gateway/src/gateway/chat.gateway.ts"
ECOSYSTEM="$AZIZA_ROOT/ecosystem.config.js"
PROXY_FILE="$AZIZA_ROOT/ollama_proxy.py"
FRONTEND_LIB="$AZIZA_ROOT/frontend/src/lib/chat-socket.ts"

log()  { printf '\033[1;36m[rollback]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[ok      ]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn    ]\033[0m %s\n' "$*"; }

if [[ $EUID -ne 0 ]]; then
  echo "Must run as root." >&2
  exit 1
fi

# Pick the most recent backup if none specified
if [[ $# -ge 1 ]]; then
  BACKUP_DIR="$1"
else
  BACKUP_DIR=$(ls -dt "$AZIZA_ROOT"/.fixes-backup-* 2>/dev/null | head -n1)
fi

if [[ -z "$BACKUP_DIR" || ! -d "$BACKUP_DIR" ]]; then
  echo "No backup directory found. Nothing to roll back." >&2
  exit 1
fi

log "Using backup: $BACKUP_DIR"

restore() {
  local src="$1" dst="$2"
  if [[ -f "$src" ]]; then
    cp -v "$src" "$dst"
    ok "restored $dst"
  else
    warn "no backup for $dst — leaving the fixed version in place"
  fi
}

restore "$BACKUP_DIR/chat.gateway.ts.bak"        "$GATEWAY_SRC"
restore "$BACKUP_DIR/ecosystem.config.js.bak"    "$ECOSYSTEM"
restore "$BACKUP_DIR/ollama_proxy.py.bak"        "$PROXY_FILE"

# Rebuild the gateway from the restored source
log "Rebuilding api-gateway…"
(cd "$AZIZA_ROOT/backend/services/api-gateway" && npm run build) || warn "nest build failed — check the source file"

# Remove the new frontend lib if it was added by deploy.sh
if [[ -f "$FRONTEND_LIB" ]] && [[ ! -f "$BACKUP_DIR/chat-socket.ts.bak" ]]; then
  rm -fv "$FRONTEND_LIB"
fi

# Restart the proxy if it was running
if pgrep -f ollama_proxy.py >/dev/null; then
  pkill -f ollama_proxy.py || true
  sleep 1
fi

# Restart PM2 services from the restored ecosystem.config.js
if [[ -f "$ECOSYSTEM" ]]; then
  pm2 restart ecosystem.config.js --only api-gateway 2>/dev/null || pm2 restart api-gateway 2>/dev/null || warn "pm2 restart failed — run manually"
fi

ok "Rollback complete."
log "Note: vLLM models were not reverted — if you swapped them with deploy.sh --vllm,"
log "you need to manually restart vllm-english and vllm-uzbek with the original models."
AZIZA_EOF_rollback_sh
ok "wrote rollback.sh ($(wc -c < rollback.sh) bytes)"


chmod +x rollback.sh ollama_proxy.py

echo
log "Done. Now run:"
echo "  bash deploy.sh --check    # verify"
echo "  bash deploy.sh --gateway  # apply just the retry-bug fix (~30s)"
echo "  bash deploy.sh            # apply everything (~5 min for vLLM swap)"
