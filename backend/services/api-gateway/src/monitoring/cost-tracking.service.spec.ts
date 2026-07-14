import { Test, TestingModule } from '@nestjs/testing';
import { CostTrackingService } from './cost-tracking.service';
import { MetricsService } from './metrics.service';
import { GpuMetricsService } from './gpu-metrics.service';

describe('CostTrackingService', () => {
  let service: CostTrackingService;
  let metricsService: MetricsService;
  let gpuMetrics: GpuMetricsService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        CostTrackingService,
        MetricsService,
        GpuMetricsService,
      ],
    }).compile();

    service = module.get<CostTrackingService>(CostTrackingService);
    metricsService = module.get<MetricsService>(MetricsService);
    gpuMetrics = module.get<GpuMetricsService>(GpuMetricsService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('getCostSummary', () => {
    it('should return cost summary with zero costs initially', () => {
      const summary = service.getCostSummary();
      
      expect(summary).toHaveProperty('totalCostUsd');
      expect(summary).toHaveProperty('estimatedMonthlyUsd');
      expect(summary).toHaveProperty('gpuUtilization');
      expect(summary).toHaveProperty('costPerInference');
      expect(summary.totalCostUsd).toBe(0);
    });
  });

  describe('getCurrentCostRate', () => {
    it('should return zero cost rate initially', () => {
      const rate = service.getCurrentCostRate();
      expect(rate).toBe(0);
    });
  });

  describe('getCostTrend', () => {
    it('should return hourly cost trend', () => {
      const trend = service.getCostTrend({ hours: 24 });
      
      expect(trend).toHaveProperty('hourly');
      expect(trend).toHaveProperty('totalHours');
      expect(trend).toHaveProperty('totalCost');
      expect(trend.totalHours).toBe(24);
      expect(Array.isArray(trend.hourly)).toBe(true);
    });
  });
});
