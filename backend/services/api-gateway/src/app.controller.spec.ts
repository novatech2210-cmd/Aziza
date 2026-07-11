import { Test, TestingModule } from '@nestjs/testing';
import { AppController } from './app.controller';
import { AppService } from './app.service';

describe('AppController', () => {
  let appController: AppController;

  const mockConnection = { readyState: 1 };

  beforeEach(async () => {
    const app: TestingModule = await Test.createTestingModule({
      controllers: [AppController],
      providers: [
        AppService,
        { provide: 'DatabaseConnection', useValue: mockConnection },
      ],
    }).compile();

    appController = app.get<AppController>(AppController);
  });

  describe('root', () => {
    it('should return health status', async () => {
      const health = await appController.getHealth();
      expect(health).toHaveProperty('status');
      expect(health.status).toBe('ok');
    });
  });
});
