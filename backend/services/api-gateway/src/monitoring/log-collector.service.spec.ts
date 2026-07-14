import { Test, TestingModule } from '@nestjs/testing';
import { getModelToken } from '@nestjs/mongoose';
import { LogCollectorService } from './log-collector.service';
import { StructuredLog } from './structured-logging.service';

describe('LogCollectorService', () => {
  let service: LogCollectorService;
  let mockLogModel: any;

  beforeEach(async () => {
    mockLogModel = {
      find: jest.fn().mockReturnThis(),
      sort: jest.fn().mockReturnThis(),
      limit: jest.fn().mockReturnThis(),
      select: jest.fn().mockReturnThis(),
      exec: jest.fn().mockResolvedValue([]),
      aggregate: jest.fn().mockResolvedValue([]),
      countDocuments: jest.fn().mockResolvedValue(0),
      insertMany: jest.fn().mockResolvedValue({}),
      deleteMany: jest.fn().mockResolvedValue({ deletedCount: 0 }),
    };

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        LogCollectorService,
        { provide: getModelToken(StructuredLog.name), useValue: mockLogModel },
      ],
    }).compile();

    service = module.get<LogCollectorService>(LogCollectorService);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('parseLogLine', () => {
    it('should parse structured JSON log lines', () => {
      const line = JSON.stringify({
        timestamp: '2026-07-14T12:00:00Z',
        level: 'INFO',
        service: 'orchestrator',
        message: 'Session started',
        correlationId: 'abc-123',
      });

      const result = (service as any).parseLogLine('orchestrator', line);
      expect(result).toBeTruthy();
      expect(result.level).toBe('info');
      expect(result.service).toBe('orchestrator');
      expect(result.message).toBe('Session started');
      expect(result.correlationId).toBe('abc-123');
    });

    it('should parse plain text log lines', () => {
      const line = '2026-07-14T12:00:00 ERROR something failed';
      const result = (service as any).parseLogLine('moshi-worker', line);
      expect(result).toBeTruthy();
      expect(result.level).toBe('error');
      expect(result.service).toBe('moshi-worker');
    });

    it('should default to info level for unparseable lines', () => {
      const line = 'random output from process';
      const result = (service as any).parseLogLine('vllm-english', line);
      expect(result).toBeTruthy();
      expect(result.level).toBe('info');
      expect(result.service).toBe('vllm-english');
    });

    it('should handle WARN level in plain text', () => {
      const line = '2026-07-14 12:00:00 WARNING: high memory usage';
      const result = (service as any).parseLogLine('personaplex', line);
      expect(result.level).toBe('warning');
    });
  });

  describe('getAggregatedLogs', () => {
    it('should query logs with default options', async () => {
      await service.getAggregatedLogs({});
      expect(mockLogModel.find).toHaveBeenCalled();
      expect(mockLogModel.sort).toHaveBeenCalledWith({ createdAt: -1 });
      expect(mockLogModel.limit).toHaveBeenCalledWith(200);
    });

    it('should apply service filter', async () => {
      await service.getAggregatedLogs({ service: 'orchestrator' });
      expect(mockLogModel.find).toHaveBeenCalledWith(
        expect.objectContaining({ service: 'orchestrator' }),
      );
    });

    it('should apply level filter', async () => {
      await service.getAggregatedLogs({ level: 'error' });
      expect(mockLogModel.find).toHaveBeenCalledWith(
        expect.objectContaining({ level: 'error' }),
      );
    });

    it('should apply time range filter', async () => {
      const start = new Date('2026-07-14T00:00:00Z');
      const end = new Date('2026-07-14T23:59:59Z');
      await service.getAggregatedLogs({ startTime: start, endTime: end });
      expect(mockLogModel.find).toHaveBeenCalledWith(
        expect.objectContaining({
          createdAt: { $gte: start, $lte: end },
        }),
      );
    });

    it('should apply custom limit', async () => {
      await service.getAggregatedLogs({ limit: 50 });
      expect(mockLogModel.limit).toHaveBeenCalledWith(50);
    });
  });

  describe('getLogStats', () => {
    it('should return aggregated stats', async () => {
      mockLogModel.aggregate
        .mockResolvedValueOnce([{ _id: 'orchestrator', count: 10 }])
        .mockResolvedValueOnce([{ _id: 'error', count: 3 }]);
      mockLogModel.countDocuments.mockResolvedValue(42);

      const result = await service.getLogStats();
      expect(result).toHaveProperty('hourly_by_service');
      expect(result).toHaveProperty('hourly_by_level');
      expect(result).toHaveProperty('total_today');
      expect(result.hourly_by_service).toEqual([{ service: 'orchestrator', count: 10 }]);
      expect(result.hourly_by_level).toEqual([{ level: 'error', count: 3 }]);
      expect(result.total_today).toBe(42);
    });
  });

  describe('cleanupOldLogs', () => {
    it('should delete logs older than 7 days', async () => {
      mockLogModel.deleteMany.mockResolvedValue({ deletedCount: 5 });
      await service.cleanupOldLogs();
      expect(mockLogModel.deleteMany).toHaveBeenCalledWith(
        expect.objectContaining({
          createdAt: expect.objectContaining({ $lt: expect.any(Date) }),
        }),
      );
    });
  });

  describe('detectServiceFromFile', () => {
    it('should detect orchestrator from log filename', () => {
      const result = (service as any).detectServiceFromFile('orchestrator-out.log');
      expect(result).toBe('orchestrator');
    });

    it('should detect moshi-worker from error log filename', () => {
      const result = (service as any).detectServiceFromFile('moshi-worker-error.log');
      expect(result).toBe('moshi-worker');
    });

    it('should return null for unknown files', () => {
      const result = (service as any).detectServiceFromFile('unknown.log');
      expect(result).toBeNull();
    });
  });
});
