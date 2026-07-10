#!/usr/bin/env node
/**
 * Aziza AI Assistant — MCP Server
 * Exposes session control, persona switching, diagnostics,
 * and text-injection tools for the full Aziza stack.
 *
 * Stack ports:
 *   8001 — PersonaPlex/Moshi (V2V)
 *   8002 — Vikhr-Llama3.1-8B (Russian T2T)
 *   8003 — alloma-3B (Uzbek T2T)
 *   8020 — Russian ASR
 *   8080 — NestJS API gateway
 *   6379 — Redis
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import Redis from "ioredis";

const redis = new Redis({ host: "127.0.0.1", port: 6379, lazyConnect: true });
redis.on("error", (err) => process.stderr.write(`[redis] ${err.message}\n`));

const NEST = "http://127.0.0.1:8080";
async function nestGet(path) { const res = await fetch(`${NEST}${path}`); return res.json(); }
async function nestPost(path, body = {}) {
  const res = await fetch(`${NEST}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return res.json();
}
async function healthCheck(label, url, timeoutMs = 2500) {
  try {
    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), timeoutMs);
    const res = await fetch(url, { signal: ctrl.signal });
    clearTimeout(tid);
    return { label, status: res.ok ? "ok" : `http_${res.status}` };
  } catch (e) { return { label, status: "down", error: e.message }; }
}
const ok = (text) => ({ content: [{ type: "text", text: typeof text === "string" ? text : JSON.stringify(text, null, 2) }] });
const fail = (msg) => ({ content: [{ type: "text", text: `ERROR: ${msg}` }], isError: true });

const server = new McpServer({ name: "aziza-mcp", version: "1.0.0" });

server.tool("check_aziza_services", "Check health of all Aziza stack services", {}, async () => {
  const [moshi, vikhr, alloma, asr, nest] = await Promise.all([
    healthCheck("personaplex_moshi_v2v", "http://127.0.0.1:8001/health"),
    healthCheck("vikhr_llama_ru_t2t",    "http://127.0.0.1:8002/health"),
    healthCheck("alloma_uz_t2t",         "http://127.0.0.1:8003/health"),
    healthCheck("asr_ru",                "http://127.0.0.1:8020/health"),
    healthCheck("nestjs_gateway",        "http://127.0.0.1:8080/health"),
  ]);
  let redisStatus = "unknown";
  try { await redis.ping(); redisStatus = "ok"; } catch (e) { redisStatus = `down: ${e.message}`; }
  const result = { moshi, vikhr, alloma, asr, nest, redis: { label: "redis", status: redisStatus } };
  const allOk = Object.values(result).every((s) => s.status === "ok");
  return ok({ overall: allOk ? "healthy" : "degraded", services: result });
});

server.tool("start_v2v_session", "Start a new PersonaPlex/Moshi V2V session",
  { user_id: z.string(), language: z.enum(["ru", "uz"]), persona: z.enum(["formal", "casual", "assistant", "tutor"]).optional().default("assistant") },
  async ({ user_id, language, persona }) => {
    try {
      const session = await nestPost("/voice/session/start", { user_id, language, persona });
      await redis.hset(`session:${session.session_id}`, { user_id, language, persona, started_at: Date.now(), status: "active" });
      return ok(session);
    } catch (e) { return fail(`Could not start session: ${e.message}`); }
  }
);

server.tool("end_v2v_session", "Terminate a V2V session", { session_id: z.string() }, async ({ session_id }) => {
  try {
    await nestPost(`/voice/session/${session_id}/end`);
    await redis.hset(`session:${session_id}`, { status: "ended", ended_at: Date.now() });
    return ok(`Session ${session_id} ended.`);
  } catch (e) { return fail(e.message); }
});

server.tool("list_active_sessions", "List all V2V sessions from Redis", {}, async () => {
  try {
    const keys = await redis.keys("session:*");
    if (!keys.length) return ok("No sessions found.");
    const sessions = await Promise.all(keys.map(async (k) => ({ session_id: k.replace("session:", ""), ...await redis.hgetall(k) })));
    return ok({ total: sessions.length, active: sessions.filter(s => s.status === "active").length, sessions });
  } catch (e) { return fail(e.message); }
});

server.tool("set_persona", "Hot-swap PersonaPlex persona for a running session",
  { session_id: z.string(), persona: z.enum(["formal", "casual", "assistant", "tutor"]) },
  async ({ session_id, persona }) => {
    try {
      await redis.hset(`session:${session_id}`, { persona, persona_updated_at: Date.now() });
      try { await nestPost(`/voice/session/${session_id}/persona`, { persona }); } catch {}
      return ok(`Persona for session ${session_id} switched to "${persona}".`);
    } catch (e) { return fail(e.message); }
  }
);

server.tool("get_session_state", "Dump full Redis state of a session", { session_id: z.string() }, async ({ session_id }) => {
  try {
    const [meta, inputQLen, outputQLen] = await Promise.all([
      redis.hgetall(`session:${session_id}`),
      redis.llen(`session:${session_id}:text_input`),
      redis.llen(`session:${session_id}:audio_output`),
    ]);
    if (!Object.keys(meta).length) return fail(`No session found: ${session_id}`);
    return ok({ session_id, meta, queues: { text_input: inputQLen, audio_output: outputQLen } });
  } catch (e) { return fail(e.message); }
});

server.tool("inject_text_to_v2v", "Push text into Moshi input queue, bypassing ASR (use while HTTPS/mic is pending)",
  { session_id: z.string(), text: z.string(), language: z.enum(["ru", "uz"]) },
  async ({ session_id, text, language }) => {
    try {
      await redis.lpush(`session:${session_id}:text_input`, JSON.stringify({ text, language, source: "mcp_inject", ts: Date.now() }));
      return ok(`Injected into session ${session_id}: "${text}" [${language}]`);
    } catch (e) { return fail(e.message); }
  }
);

server.tool("probe_uzbek_tokenizer", "Test alloma-3B for APST token bleed",
  { prompt: z.string().default("Salom, qanday yordam bera olaman?") },
  async ({ prompt }) => {
    try {
      const res = await fetch("http://127.0.0.1:8003/v1/completions", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: "alloma", prompt, max_tokens: 100, temperature: 0.1, stop: ["<|im_end|>", "<|endoftext|>"] }),
      });
      const data = await res.json();
      const raw = data?.choices?.[0]?.text ?? JSON.stringify(data);
      return ok({ prompt, raw_completion: raw, apst_bleed_detected: /APST|<\|im_start\||<\|im_end\|/.test(raw) });
    } catch (e) { return fail(`alloma-3B unreachable: ${e.message}`); }
  }
);

server.tool("pm2_status", "Get PM2 process list", {}, async () => {
  try {
    const { execSync } = await import("child_process");
    const out = execSync("pm2 jlist 2>/dev/null", { encoding: "utf8" });
    const procs = JSON.parse(out).map((p) => ({
      name: p.name, status: p.pm2_env?.status, pid: p.pid,
      restarts: p.pm2_env?.restart_time, cpu: p.monit?.cpu,
      mem_mb: p.monit?.memory ? Math.round(p.monit.memory / 1024 / 1024) : null,
    }));
    return ok(procs);
  } catch (e) { return fail(`pm2 error: ${e.message}`); }
});

server.tool("pm2_restart", "Restart a PM2 process by name", { process_name: z.string() }, async ({ process_name }) => {
  try {
    const { execSync } = await import("child_process");
    execSync(`pm2 restart ${process_name}`, { encoding: "utf8" });
    return ok(`Restarted: ${process_name}`);
  } catch (e) { return fail(e.message); }
});

const transport = new StdioServerTransport();
await server.connect(transport);
process.stderr.write("[aziza-mcp] Server running on stdio\n");
