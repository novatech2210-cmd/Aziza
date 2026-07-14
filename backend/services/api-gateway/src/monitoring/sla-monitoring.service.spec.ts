import { Test, TestingModule } from '@nestjs/testing';
import { SLAMonitoringService } from './sla-monitoring.service';
import { MetricsService } from './metrics.service';
import { HealthCheckService } from './health-check.service';

describe('SLAMonitoringService', () => {
  let service: SLAMonitoringService;
  let metricsService: MetricsService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        SLAMonitoringService,
        MetricsService,
        {
          provide: HealthCheckService,
          useValue: {
            getAllServiceHealth: jest.fn().mockResolvedValue([]),
          },
        },
      ],
    }).compile();

    service = module.get<SLAMonitoringService>(SLAMonitoringService);
    metricsService = module.get<MetricsService>(MetricsService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('getCurrentSLA', () => {
    it('should return no data message initially', () => {
      const sla = service.getCurrentSLA();
      expect(sla.status).toBe('no_data');
    });
  });

  describe('getSLATrend', () => {
    it('should return SLA trend with zero values initially', () => {
      const trend = service.getSLATrend({ hours: 24 });
      
      expect(trend).toHaveProperty('reports');
      expect(trend).toHaveProperty('averageScore');
      expect(trend).toHaveProperty('minScore');
      expect(trend).toHaveProperty('breaches');
      expect(trend.reports).toHaveLength(0);
      expect(trend.averageScore).toBe(0);
    });
  });

  describe('generateReport', () => {
    it('should generate a report with metrics', async () => {
      // Add some metrics
      for (let i = 0; i < 10; i++) {
        metricsService.recordRequest({
          timestamp: Date.now() / 1000,
          ttftMs: 100 + i * 10,
          tokensPerSec: 20,
          service: 'vllm:8002',
          language: 'en',
          success: true,
        });
      }

      await service.generateReport();
      const sla = service.getCurrentSLA();
      
      expect(sla.status).not.toBe('no_data');
      expect(sla).toHaveProperty('score');
      expect(sla).toHaveProperty('uptime');
      expect(sla).toHaveProperty('targets');
    });
  });
});
