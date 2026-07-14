import { MetricsService, RequestMetric } from './metrics.service';

describe('MetricsService', () => {
  let service: MetricsService;

  beforeEach(() => {
    service = new MetricsService();
  });

  describe('recordRequest', () => {
    it('should record a successful request', () => {
      const metric: RequestMetric = {
        timestamp: Date.now() / 1000,
        ttftMs: 150,
        tokensPerSec: 50,
        service: 'vllm:8002',
        language: 'ru',
        success: true,
      };

      service.recordRequest(metric);

      const summary = service.getMetricsSummary();
      expect(summary.total_requests).toBe(1);
      expect(summary.total_errors).toBe(0);
    });

    it('should record an error request', () => {
      const metric: RequestMetric = {
        timestamp: Date.now() / 1000,
        ttftMs: 0,
        tokensPerSec: 0,
        service: 'vllm:8002',
        language: 'en',
        success: false,
        error: 'Connection refused',
      };

      service.recordRequest(metric);

      const summary = service.getMetricsSummary();
      expect(summary.total_requests).toBe(1);
      expect(summary.total_errors).toBe(1);
      expect(summary.error_rate).toBe(100);
    });

    it('should track error rate correctly', () => {
      // 3 successful + 1 error = 25% error rate
      for (let i = 0; i < 3; i++) {
        service.recordRequest({
          timestamp: Date.now() / 1000,
          ttftMs: 100,
          tokensPerSec: 60,
          service: 'vllm:8002',
          language: 'ru',
          success: true,
        });
      }
      service.recordRequest({
        timestamp: Date.now() / 1000,
        ttftMs: 0,
        tokensPerSec: 0,
        service: 'vllm:8002',
        language: 'ru',
        success: false,
        error: 'timeout',
      });

      const summary = service.getMetricsSummary();
      expect(summary.total_requests).toBe(4);
      expect(summary.total_errors).toBe(1);
      expect(summary.error_rate).toBe(25);
    });
  });

  describe('getMetricsSummary', () => {
    it('should return zeroed metrics when no data', () => {
      const summary = service.getMetricsSummary();
      expect(summary.total_requests).toBe(0);
      expect(summary.total_errors).toBe(0);
      expect(summary.ttft.p50).toBeNull();
      expect(summary.ttft.p95).toBeNull();
      expect(summary.tokens_per_sec.p50).toBeNull();
      expect(summary.success_rate).toBe(100);
    });

    it('should calculate TTFT percentiles', () => {
      // Insert 100 requests with known TTFT values
      for (let i = 0; i < 100; i++) {
        service.recordRequest({
          timestamp: Date.now() / 1000,
          ttftMs: i * 10, // 0, 10, 20, ..., 990
          tokensPerSec: 50,
          service: 'vllm:8002',
          language: 'ru',
          success: true,
        });
      }

      const summary = service.getMetricsSummary();
      expect(summary.ttft.avg).toBeGreaterThan(0);
      expect(summary.ttft.p50).toBeGreaterThan(0);
      expect(summary.ttft.p95).toBeGreaterThan(summary.ttft.p50!);
    });

    it('should calculate tokens per sec averages', () => {
      for (let i = 0; i < 5; i++) {
        service.recordRequest({
          timestamp: Date.now() / 1000,
          ttftMs: 100,
          tokensPerSec: (i + 1) * 20, // 20, 40, 60, 80, 100
          service: 'vllm:8002',
          language: 'ru',
          success: true,
        });
      }

      const summary = service.getMetricsSummary();
      expect(summary.tokens_per_sec.avg).toBe(60);
    });
  });

  describe('getLatencyHeatmap', () => {
    it('should return 24 hour heatmap', () => {
      const heatmap = service.getLatencyHeatmap();
      expect(heatmap).toHaveLength(24);
      expect(heatmap[0]).toHaveProperty('hour');
      expect(heatmap[0]).toHaveProperty('latency');
      expect(heatmap[0]).toHaveProperty('requests');
    });

    it('should aggregate latency by hour', () => {
      const now = Date.now() / 1000;
      for (let i = 0; i < 5; i++) {
        service.recordRequest({
          timestamp: now,
          ttftMs: 200,
          tokensPerSec: 50,
          service: 'vllm:8002',
          language: 'ru',
          success: true,
        });
      }

      const heatmap = service.getLatencyHeatmap();
      const totalRequests = heatmap.reduce((sum, h) => sum + h.requests, 0);
      expect(totalRequests).toBe(5);
    });
  });

  describe('getRecentErrors', () => {
    it('should return recent errors in reverse order', () => {
      for (let i = 0; i < 3; i++) {
        service.recordRequest({
          timestamp: Date.now() / 1000,
          ttftMs: 0,
          tokensPerSec: 0,
          service: 'vllm:8002',
          language: 'ru',
          success: false,
          error: `error-${i}`,
        });
      }

      const errors = service.getRecentErrors(2);
      expect(errors).toHaveLength(2);
      expect(errors[0].error).toBe('error-2');
      expect(errors[1].error).toBe('error-1');
    });

    it('should only return error requests', () => {
      service.recordRequest({
        timestamp: Date.now() / 1000,
        ttftMs: 100,
        tokensPerSec: 50,
        service: 'vllm:8002',
        language: 'ru',
        success: true,
      });
      service.recordRequest({
        timestamp: Date.now() / 1000,
        ttftMs: 0,
        tokensPerSec: 0,
        service: 'vllm:8002',
        language: 'en',
        success: false,
        error: 'bad request',
      });

      const errors = service.getRecentErrors();
      expect(errors).toHaveLength(1);
      expect(errors[0].error).toBe('bad request');
    });

    it('should default to Unknown error', () => {
      service.recordRequest({
        timestamp: Date.now() / 1000,
        ttftMs: 0,
        tokensPerSec: 0,
        service: 'vllm:8002',
        language: 'ru',
        success: false,
      });

      const errors = service.getRecentErrors();
      expect(errors[0].error).toBe('Unknown error');
    });
  });
});
