import { Injectable, Logger } from '@nestjs/common';

export interface RequestMetric {
  timestamp: number;
  ttftMs: number;
  tokensPerSec: number;
  service: string;
  language: string;
  success: boolean;
  error?: string;
}

@Injectable()
export class MetricsService {
  private readonly logger = new Logger(MetricsService.name);
  
  // In-memory ring buffers (last 1000 entries)
  private readonly requestMetrics: RequestMetric[] = [];
  private readonly MAX_METRICS = 1000;
  
  // Counters
  private totalRequests = 0;
  private totalErrors = 0;
  private readonly hourlyStats: Map<string, { requests: number; errors: number; ttftSum: number }> = new Map();

  recordRequest(metric: RequestMetric) {
    this.requestMetrics.push(metric);
    if (this.requestMetrics.length > this.MAX_METRICS) {
      this.requestMetrics.shift();
    }

    this.totalRequests++;
    if (!metric.success) {
      this.totalErrors++;
    }

    // Update hourly stats
    const hourKey = new Date(metric.timestamp * 1000).toISOString().slice(0, 13);
    if (!this.hourlyStats.has(hourKey)) {
      this.hourlyStats.set(hourKey, { requests: 0, errors: 0, ttftSum: 0 });
    }
    const stats = this.hourlyStats.get(hourKey)!;
    stats.requests++;
    if (!metric.success) stats.errors++;
    stats.ttftSum += metric.ttftMs;

    // Clean old hourly stats (keep last 24 hours)
    const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().slice(0, 13);
    for (const key of this.hourlyStats.keys()) {
      if (key < cutoff) this.hourlyStats.delete(key);
    }
  }

  getMetricsSummary() {
    const now = Date.now() / 1000;
    const lastMinute = now - 60;
    const lastHour = now - 3600;

    const recentMetrics = this.requestMetrics.filter(m => m.timestamp > lastMinute);
    const hourMetrics = this.requestMetrics.filter(m => m.timestamp > lastHour);

    // Calculate percentiles for last hour
    const ttfts = hourMetrics.map(m => m.ttftMs).sort((a, b) => a - b);
    const tokensPerSec = hourMetrics.map(m => m.tokensPerSec).filter(t => t > 0).sort((a, b) => a - b);

    const percentile = (arr: number[], p: number) => {
      if (arr.length === 0) return null;
      const idx = Math.ceil((p / 100) * arr.length) - 1;
      return arr[Math.max(0, idx)];
    };

    return {
      total_requests: this.totalRequests,
      total_errors: this.totalErrors,
      error_rate: this.totalRequests > 0 ? Math.round((this.totalErrors / this.totalRequests) * 100) : 0,
      requests_last_minute: recentMetrics.length,
      requests_last_hour: hourMetrics.length,
      ttft: {
        p50: percentile(ttfts, 50),
        p95: percentile(ttfts, 95),
        p99: percentile(ttfts, 99),
        avg: ttfts.length > 0 ? Math.round(ttfts.reduce((a, b) => a + b, 0) / ttfts.length) : null,
      },
      tokens_per_sec: {
        p50: percentile(tokensPerSec, 50),
        p95: percentile(tokensPerSec, 95),
        avg: tokensPerSec.length > 0 ? Math.round(tokensPerSec.reduce((a, b) => a + b, 0) / tokensPerSec.length) : null,
      },
      success_rate: hourMetrics.length > 0 
        ? Math.round((hourMetrics.filter(m => m.success).length / hourMetrics.length) * 100)
        : 100,
    };
  }

  getLatencyHeatmap() {
    const now = Date.now() / 1000;
    const heatmap: { hour: string; latency: number; requests: number }[] = [];

    for (let i = 23; i >= 0; i--) {
      const hourStart = now - (i + 1) * 3600;
      const hourEnd = now - i * 3600;
      const hourMetrics = this.requestMetrics.filter(
        m => m.timestamp > hourStart && m.timestamp <= hourEnd
      );

      const ttfts = hourMetrics.map(m => m.ttftMs);
      const avgLatency = ttfts.length > 0 
        ? Math.round(ttfts.reduce((a, b) => a + b, 0) / ttfts.length)
        : 0;

      const hour = new Date(hourEnd * 1000).getHours();
      heatmap.push({
        hour: `${hour.toString().padStart(2, '0')}:00`,
        latency: avgLatency,
        requests: hourMetrics.length,
      });
    }

    return heatmap;
  }

  getRecentErrors(limit = 50) {
    return this.requestMetrics
      .filter(m => !m.success)
      .slice(-limit)
      .reverse()
      .map(m => ({
        timestamp: new Date(m.timestamp * 1000).toISOString(),
        service: m.service,
        language: m.language,
        error: m.error || 'Unknown error',
      }));
  }
}
