import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { ConfigModule } from '@nestjs/config';
import { MongooseModule } from '@nestjs/mongoose';
import { AuthModule } from '../src/auth/auth.module';
import { MonitoringModule } from '../src/monitoring/monitoring.module';
import { AppController } from '../src/app.controller';
import { AppService } from '../src/app.service';

describe('Auth API (e2e)', () => {
  let app: INestApplication;
  let jwtToken: string;
  const testEmail = `test_${Date.now()}@example.com`;
  const testPassword = 'Test1234!';

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
  }, 30000);

  afterAll(async () => {
    if (app) await app.close();
  });

  describe('POST /auth/register', () => {
    it('should register a new user', () => {
      return request(app.getHttpServer())
        .post('/auth/register')
        .send({ email: testEmail, password: testPassword })
        .expect(201)
        .expect((res) => {
          expect(res.body).toHaveProperty('access_token');
          expect(res.body).toHaveProperty('user');
          expect(res.body.user.email).toBe(testEmail);
          expect(res.body.user.role).toBe('user');
          expect(res.body.user).toHaveProperty('id');
        });
    });

    it('should reject duplicate email', () => {
      return request(app.getHttpServer())
        .post('/auth/register')
        .send({ email: testEmail, password: testPassword })
        .expect(409)
        .expect((res) => {
          expect(res.body.message).toMatch(/already registered|conflict/i);
        });
    });

    it('should reject invalid email format', () => {
      return request(app.getHttpServer())
        .post('/auth/register')
        .send({ email: 'not-an-email', password: testPassword })
        .expect(400);
    });

    it('should reject short password', () => {
      return request(app.getHttpServer())
        .post('/auth/register')
        .send({ email: 'short@example.com', password: '123' })
        .expect(400);
    });

    it('should reject missing email', () => {
      return request(app.getHttpServer())
        .post('/auth/register')
        .send({ password: testPassword })
        .expect(400);
    });
  });

  describe('POST /auth/login', () => {
    it('should login with valid credentials', () => {
      return request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: testEmail, password: testPassword })
        .expect(201)
        .expect((res) => {
          expect(res.body).toHaveProperty('access_token');
          expect(res.body).toHaveProperty('user');
          expect(res.body.user.email).toBe(testEmail);
          jwtToken = res.body.access_token;
        });
    });

    it('should reject wrong password', () => {
      return request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: testEmail, password: 'WrongPassword!' })
        .expect(401)
        .expect((res) => {
          expect(res.body.message).toMatch(/invalid|unauthorized/i);
        });
    });

    it('should reject non-existent email', () => {
      return request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: 'nonexistent@example.com', password: testPassword })
        .expect(401);
    });
  });

  describe('GET /auth/me', () => {
    it('should return current user with valid token', () => {
      return request(app.getHttpServer())
        .get('/auth/me')
        .set('Authorization', `Bearer ${jwtToken}`)
        .expect(200)
        .expect((res) => {
          expect(res.body.email).toBe(testEmail);
          expect(res.body.role).toBe('user');
        });
    });

    it('should reject request without token', () => {
      return request(app.getHttpServer())
        .get('/auth/me')
        .expect(401);
    });

    it('should reject request with invalid token', () => {
      return request(app.getHttpServer())
        .get('/auth/me')
        .set('Authorization', 'Bearer invalid_token_here')
        .expect(401);
    });
  });

  describe('POST /auth/refresh', () => {
    it('should refresh token', () => {
      return request(app.getHttpServer())
        .post('/auth/refresh')
        .set('Authorization', `Bearer ${jwtToken}`)
        .expect(201)
        .expect((res) => {
          expect(res.body).toHaveProperty('access_token');
        });
    });
  });

  describe('GET /auth/me/tier', () => {
    it('should return tier for authenticated user', () => {
      return request(app.getHttpServer())
        .get('/auth/me/tier')
        .set('Authorization', `Bearer ${jwtToken}`)
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('tier');
          expect(['free', 'enterprise']).toContain(res.body.tier);
        });
    });
  });
});
