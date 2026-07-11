import { Test, TestingModule } from '@nestjs/testing';
import { AlertingService } from './alerting.service';
import { MetricsService } from './metrics.service';
import { ErrorAggregationService } from './error-aggregation.service';
import { HealthCheckService } from './health-check.service';

describe('AlertingService', () => {
  let service: AlertingService;

  const mockMetricsService = {
    getMetricsSummary: jest.fn().mockReturnValue({
      total_requests: 100,
      total_errors: 5,
      error_rate: 0.05,
      ttft: { p50: 200, p95: 500, p99: 800 },
      tokens_per_sec: { avg: 25 },
    }),
  };

  const mockErrorService = {
    logWarning: jest.fn().mockResolvedValue(undefined),
    getErrors: jest.fn().mockReturnValue([]),
  };

  const mockHealthService = {
    checkAll: jest.fn().mockReturnValue({}),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AlertingService,
        { provide: MetricsService, useValue: mockMetricsService },
        { provide: ErrorAggregationService, useValue: mockErrorService },
        { provide: HealthCheckService, useValue: mockHealthService },
      ],
    }).compile();

    service = module.get<AlertingService>(AlertingService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('getAlerts', () => {
    it('returns empty array when no alerts', () => {
      expect(service.getAlerts()).toEqual([]);
    });

    it('respects limit option', () => {
      expect(service.getAlerts({ limit: 5 })).toEqual([]);
    });
  });

  describe('getAlertStats', () => {
    it('returns stats structure', () => {
      const stats = service.getAlertStats();
      expect(stats).toHaveProperty('total');
      expect(stats).toHaveProperty('hourly');
      expect(stats).toHaveProperty('daily');
      expect(stats).toHaveProperty('unresolved');
    });
  });
});
