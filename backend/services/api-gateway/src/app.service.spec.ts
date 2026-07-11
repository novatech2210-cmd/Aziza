import { Test, TestingModule } from '@nestjs/testing';
import { AppService } from './app.service';

describe('AppService', () => {
  let service: AppService;

  const mockConnection = { readyState: 1 };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AppService,
        { provide: 'DatabaseConnection', useValue: mockConnection },
      ],
    }).compile();

    service = module.get<AppService>(AppService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('getHealth', () => {
    it('should return ok when mongo is connected', async () => {
      const health = await service.getHealth();
      expect(health.status).toBe('ok');
      expect(health.mongo).toBe('connected');
    });

    it('should return degraded when mongo is disconnected', async () => {
      (mockConnection as any).readyState = 0;
      const health = await service.getHealth();
      expect(health.status).toBe('degraded');
      expect(health.mongo).toBe('disconnected');
      (mockConnection as any).readyState = 1;
    });
  });
});
