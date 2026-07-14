import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { ConfigModule } from '@nestjs/config';
import { MongooseModule } from '@nestjs/mongoose';
import { AuthModule } from '../src/auth/auth.module';
import { MonitoringModule } from '../src/monitoring/monitoring.module';
import { AppController } from '../src/app.controller';
import { AppService } from '../src/app.service';

describe('Chat API (e2e)', () => {
  let app: INestApplication;
  let jwtToken: string;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [
        ConfigModule.forRoot({ isGlobal: true }),
        MongooseModule.forRoot(process.env.MONGODB_URI || 'mongodb://localhost:27017/aziza_test'),
        AuthModule,
        MonitoringModule,
      ],
      controllers: [AppController],
      providers: [AppService],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(new ValidationPipe({ transform: true, whitelist: true }));
    await app.init();

    const testEmail = `chat_${Date.now()}@example.com`;
    const loginRes = await request(app.getHttpServer())
      .post('/auth/register')
      .send({ email: testEmail, password: 'Chat1234!' });

    jwtToken = loginRes.body.access_token;
  }, 30000);

  afterAll(async () => {
    if (app) await app.close();
  });

  describe('Auth endpoints', () => {
    it('should register and login', async () => {
      const email = `chat2_${Date.now()}@example.com`;
      const registerRes = await request(app.getHttpServer())
        .post('/auth/register')
        .send({ email, password: 'Chat1234!' })
        .expect(201);

      expect(registerRes.body).toHaveProperty('access_token');
      expect(registerRes.body.user.email).toBe(email);
    });
  });
});
