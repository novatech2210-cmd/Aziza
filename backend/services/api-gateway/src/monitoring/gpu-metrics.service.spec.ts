import { GpuMetricsService } from './gpu-metrics.service';

describe('GpuMetricsService', () => {
  let service: GpuMetricsService;

  beforeEach(() => {
    service = new GpuMetricsService();
  });

  describe('getGpuMetrics', () => {
    it('should return an array', async () => {
      const metrics = await service.getGpuMetrics();
      expect(Array.isArray(metrics)).toBe(true);
    });

    it('should cache results for 2 seconds', async () => {
      const first = await service.getGpuMetrics();
      const second = await service.getGpuMetrics();
      expect(first).toBe(second);
    });

    it('should refresh after cache expires', async () => {
      const first = await service.getGpuMetrics();
      await new Promise(resolve => setTimeout(resolve, 2100));
      const second = await service.getGpuMetrics();
      expect(second).not.toBe(first);
    });
  });

  describe('getGpuSummary', () => {
    it('should return available field', async () => {
      const summary = await service.getGpuSummary();
      expect(summary).toHaveProperty('available');
      expect(typeof summary.available).toBe('boolean');
    });

    it('should return gpus array', async () => {
      const summary = await service.getGpuSummary();
      expect(Array.isArray(summary.gpus)).toBe(true);
    });

    it('should return gpu objects with correct shape when GPUs exist', async () => {
      const summary = await service.getGpuSummary();
      if (summary.available && summary.gpus.length > 0) {
        const gpu = summary.gpus[0];
        expect(gpu).toHaveProperty('index');
        expect(gpu).toHaveProperty('name');
        expect(gpu).toHaveProperty('memory');
        expect(gpu).toHaveProperty('utilization');
        expect(gpu).toHaveProperty('temperature');
        expect(gpu).toHaveProperty('power');
        expect(gpu.memory).toHaveProperty('total');
        expect(gpu.memory).toHaveProperty('used');
        expect(gpu.memory).toHaveProperty('free');
        expect(gpu.memory).toHaveProperty('percentUsed');
        expect(gpu.power).toHaveProperty('draw');
        expect(gpu.power).toHaveProperty('limit');
        expect(gpu.power).toHaveProperty('percentUsed');
      }
    });

    it('should return cached result within TTL', async () => {
      const first = await service.getGpuSummary();
      const second = await service.getGpuSummary();
      expect(first).toEqual(second);
    });
  });
});
