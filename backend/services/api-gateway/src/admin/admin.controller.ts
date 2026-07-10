import {
  Controller,
  Get,
  Delete,
  Param,
  Post,
  Body,
} from '@nestjs/common';

// ---------------------------------------------------------------------------
// In-memory latency ring buffer (last 60 response times in ms)
// ---------------------------------------------------------------------------
const latencyBuf: number[] = [];
const MAX_BUF = 60;

export function recordLatency(ms: number) {
  latencyBuf.push(ms);
  if (latencyBuf.length > MAX_BUF) latencyBuf.shift();
}

function percentile(sorted: number[], pct: number): number | null {
  if (!sorted.length) return null;
  const idx = Math.ceil((pct / 100) * sorted.length) - 1;
  return sorted[Math.max(0, idx)];
}

// ---------------------------------------------------------------------------
// In-memory RAG document store (plain strings, good enough for Phase 4)
// ---------------------------------------------------------------------------
interface RagDoc {
  id: string;
  text: string;
  ingestedAt: string;
}
const ragDocs: RagDoc[] = [];

// ---------------------------------------------------------------------------
// In-memory error log (filled by other services via import of addError)
// ---------------------------------------------------------------------------
interface ErrorEntry {
  ts: string;
  ts_epoch: number;
  level: string;
  service: string;
  message: string;
}
export const errorLog: ErrorEntry[] = [];

export function addError(service: string, message: string, level = 'error') {
  const now = Date.now() / 1000;
  errorLog.push({
    ts: new Date().toISOString(),
    ts_epoch: now,
    level,
    service,
    message,
  });
  // keep last 500
  if (errorLog.length > 500) errorLog.shift();
}

@Controller('admin')
export class AdminController {
  // ── Sessions ─────────────────────────────────────────────────────────────

  @Get('sessions')
  getSessions() {
    return [];
  }

  @Delete('sessions')
  deleteAllSessions() {
    return { deleted: 0 };
  }

  @Delete('sessions/:id')
  deleteSession(@Param('id') id: string) {
    return { success: true, id };
  }

  // ── Metrics ───────────────────────────────────────────────────────────────

  @Get('metrics')
  getMetrics() {
    const sorted = [...latencyBuf].sort((a, b) => a - b);
    const now = Date.now() / 1000;
    const minute_ago = now - 60;
    const recentErrors = errorLog.filter((e) => e.ts_epoch > minute_ago).length;

    return {
      p50: percentile(sorted, 50),
      p95: percentile(sorted, 95),
      p99: percentile(sorted, 99),
      error_rate: recentErrors,
      requests_total: latencyBuf.length,
    };
  }

  // ── Errors ────────────────────────────────────────────────────────────────

  @Get('errors')
  getErrors() {
    return [...errorLog].sort((a, b) => b.ts_epoch - a.ts_epoch).slice(0, 500);
  }

  // ── Latency heatmap ───────────────────────────────────────────────────────

  @Get('latency/heatmap')
  getLatencyHeatmap() {
    return Array.from({ length: 24 }).map((_, hour) => ({
      hour: `${hour.toString().padStart(2, '0')}:00`,
      latency: Math.floor(Math.random() * 100) + 20,
    }));
  }

  // ── RAG ───────────────────────────────────────────────────────────────────

  @Get('rag/stats')
  getRagStats() {
    const totalBytes = ragDocs.reduce((s, d) => s + d.text.length, 0);
    return {
      doc_count: ragDocs.length,
      index_size_bytes: totalBytes,
      last_updated: ragDocs.length ? ragDocs[ragDocs.length - 1].ingestedAt : null,
    };
  }

  @Post('rag/ingest')
  ragIngest(@Body() body: { texts?: string[] }) {
    const texts = body?.texts ?? [];
    const added: string[] = [];
    for (const text of texts) {
      const id = `doc-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      ragDocs.push({ id, text, ingestedAt: new Date().toISOString() });
      added.push(id);
    }
    return { ingested: added.length, ids: added };
  }

  @Delete('rag/clear')
  ragClear() {
    const count = ragDocs.length;
    ragDocs.length = 0;
    return { cleared: count };
  }
}
