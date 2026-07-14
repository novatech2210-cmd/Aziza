import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { ConfigModule } from '@nestjs/config';
import { MongooseModule } from '@nestjs/mongoose';
import { AuthModule } from '../src/auth/auth.module';
import { MonitoringModule } from '../src/monitoring/monitoring.module';
import { AdminController } from '../src/admin/admin.controller';
import { AppController } from '../src/app.controller';
import { AppService } from '../src/app.service';
import { V2VGateway } from '../src/gateway/v2v.gateway';
import { GpuMetricsService } from '../src/monitoring/gpu-metrics.service';
import { MetricsService } from '../src/monitoring/metrics.service';
import { ErrorAggregationService } from '../src/monitoring/error-aggregation.service';
import { HealthCheckService } from '../src/monitoring/health-check.service';
import { StructuredLoggingService } from '../src/monitoring/structured-logging.service';
import { AlertingService } from '../src/monitoring/alerting.service';
import { CostTrackingService } from '../src/monitoring/cost-tracking.service';
import { SLAMonitoringService } from '../src/monitoring/sla-monitoring.service';

// Mock V2VGateway for e2e tests (avoids Redis connection)
const mockV2VGateway = {
  getMetrics: () => ({
    totalConnections: 0,
    activeConnections: 0,
    totalSessions: 0,
    averageSessionDurationMs: 0,
    sessionsCompleted: 0,
    totalAudioBytesIn: 0,
    totalAudioBytesOut: 0,
    errors: 0,
    activeSessions: 0,
  }),
};

const mockGpuMetricsService = {
  getGpuMetrics: async () => [],
  getGpuSummary: () => ({ available: false, gpus: [] }),
};

const mockMetricsService = {
  recordRequest: () => {},
  getMetricsSummary: () => ({
    total_requests: 0,
    total_errors: 0,
    error_rate: 0,
    requests_last_minute: 0,
    requests_last_hour: 0,
    ttft: { p50: null, p95: null, p99: null, avg: null },
    tokens_per_sec: { p50: null, p95: null, avg: null },
    success_rate: 100,
  }),
  getLatencyHeatmap: () => Array.from({ length: 24 }, (_, i) => ({
    hour: `${i.toString().padStart(2, '0')}:00`,
    latency: 0,
    requests: 0,
  })),
  getRecentErrors: () => [],
};

const mockErrorAggregationService = {
  logError: async () => {},
  logWarning: async () => {},
  getRecentErrors: async () => [],
  getErrorStats: async () => ({
    hourly_by_service: [],
    daily_by_service: [],
    total_unresolved: 0,
  }),
  markResolved: async () => null,
};

const mockHealthCheckService = {
  registerService: () => {},
  checkService: async () => ({
    status: 'healthy' as const,
    service: 'test',
    timestamp: new Date().toISOString(),
    checks: {},
  }),
  getServiceHealth: async () => null,
  getAllServiceHealth: async () => [],
};

const mockStructuredLoggingService = {
  log: async () => {},
  info: async () => {},
  warn: async () => {},
  error: async () => {},
  getLogs: async () => [],
  getLogStats: async () => ({
    hourly_by_service: [],
    daily_by_service: [],
    hourly_by_level: [],
  }),
};

const mockAlertingService = {
  getAlerts: () => [],
  getAlertStats: () => ({
    total: 0,
    unresolved: 0,
    hourly: { total: 0, critical: 0, warning: 0, info: 0 },
    daily: { total: 0, critical: 0, warning: 0, info: 0 },
    by_service: {},
  }),
  resolveAlert: () => ({ success: true }),
  clearResolvedAlerts: () => ({ cleared: 0 }),
};

const mockCostTrackingService = {
  getCostSummary: () => ({
    hourly: [],
    daily: [],
    totalCostUsd: 0,
    estimatedMonthlyUsd: 0,
    gpuUtilization: 0,
    costPerInference: 0,
  }),
  getCostTrend: () => ({ hourly: [], totalHours: 24, totalCost: 0 }),
  getCurrentCostRate: () => 0,
};

const mockSLAMonitoringService = {
  getCurrentSLA: () => ({ status: 'no_data', message: 'No data' }),
  getSLATrend: () => ({
    reports: [],
    averageScore: 0,
    minScore: 0,
    breaches: 0,
  }),
};

describe('Admin API (e2e)', () => {
  let app: INestApplication;
  let adminToken: string;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [
        ConfigModule.forRoot({ isGlobal: true }),
        MongooseModule.forRoot(process.env.MONGODB_URI || 'mongodb://localhost:27017/aziza_test'),
        AuthModule,
      ],
      controllers: [AdminController, AppController],
      providers: [
        AppService,
        { provide: V2VGateway, useValue: mockV2VGateway },
        { provide: GpuMetricsService, useValue: mockGpuMetricsService },
        { provide: MetricsService, useValue: mockMetricsService },
        { provide: ErrorAggregationService, useValue: mockErrorAggregationService },
        { provide: HealthCheckService, useValue: mockHealthCheckService },
        { provide: StructuredLoggingService, useValue: mockStructuredLoggingService },
        { provide: AlertingService, useValue: mockAlertingService },
        { provide: CostTrackingService, useValue: mockCostTrackingService },
        { provide: SLAMonitoringService, useValue: mockSLAMonitoringService },
      ],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(new ValidationPipe({ transform: true, whitelist: true }));
    await app.init();

    const adminEmail = `admin_${Date.now()}@example.com`;
    const adminPassword = 'Admin1234!';

    await request(app.getHttpServer())
      .post('/auth/register')
      .send({ email: adminEmail, password: adminPassword, role: 'admin' });

    const loginRes = await request(app.getHttpServer())
      .post('/auth/login')
      .send({ email: adminEmail, password: adminPassword });

    adminToken = loginRes.body.access_token;
  }, 30000);

  afterAll(async () => {
    if (app) await app.close();
  });

  describe('GET /admin/sessions', () => {
    it('should return sessions list for admin', () => {
      return request(app.getHttpServer())
        .get('/admin/sessions')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200)
        .expect((res) => {
          expect(Array.isArray(res.body)).toBe(true);
        });
    });

    it('should reject unauthenticated request', () => {
      return request(app.getHttpServer())
        .get('/admin/sessions')
        .expect(401);
    });
  });

  describe('GET /admin/gpu', () => {
    it('should return GPU metrics for admin', () => {
      return request(app.getHttpServer())
        .get('/admin/gpu')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('available');
          expect(typeof res.body.available).toBe('boolean');
        });
    });
  });

  describe('GET /admin/metrics', () => {
    it('should return request metrics', () => {
      return request(app.getHttpServer())
        .get('/admin/metrics')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('total_requests');
          expect(res.body).toHaveProperty('error_rate');
          expect(res.body).toHaveProperty('ttft');
          expect(res.body).toHaveProperty('tokens_per_sec');
        });
    });
  });

  describe('GET /admin/latency/heatmap', () => {
    it('should return latency heatmap', () => {
      return request(app.getHttpServer())
        .get('/admin/latency/heatmap')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200)
        .expect((res) => {
          expect(Array.isArray(res.body)).toBe(true);
          expect(res.body).toHaveLength(24);
        });
    });
  });

  describe('GET /admin/errors', () => {
    it('should return recent errors', () => {
      return request(app.getHttpServer())
        .get('/admin/errors')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200)
        .expect((res) => {
          expect(Array.isArray(res.body)).toBe(true);
        });
    });
  });

  describe('GET /admin/health', () => {
    it('should return health status', () => {
      return request(app.getHttpServer())
        .get('/admin/health')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200);
    });
  });

  describe('GET /admin/logs', () => {
    it('should return structured logs', () => {
      return request(app.getHttpServer())
        .get('/admin/logs')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200)
        .expect((res) => {
          expect(Array.isArray(res.body)).toBe(true);
        });
    });
  });

  describe('GET /admin/alerts', () => {
    it('should return alerts', () => {
      return request(app.getHttpServer())
        .get('/admin/alerts')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200)
        .expect((res) => {
          expect(Array.isArray(res.body)).toBe(true);
        });
    });
  });

  describe('GET /admin/alerts/stats', () => {
    it('should return alert stats', () => {
      return request(app.getHttpServer())
        .get('/admin/alerts/stats')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('total');
          expect(res.body).toHaveProperty('unresolved');
          expect(res.body).toHaveProperty('hourly');
          expect(res.body).toHaveProperty('daily');
        });
    });
  });

  describe('GET /admin/costs', () => {
    it('should return cost summary', () => {
      return request(app.getHttpServer())
        .get('/admin/costs')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('totalCostUsd');
          expect(res.body).toHaveProperty('estimatedMonthlyUsd');
          expect(res.body).toHaveProperty('gpuUtilization');
          expect(res.body).toHaveProperty('costPerInference');
        });
    });
  });

  describe('GET /admin/sla', () => {
    it('should return SLA status', () => {
      return request(app.getHttpServer())
        .get('/admin/sla')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('status');
        });
    });
  });

  describe('GET /admin/v2v/metrics', () => {
    it('should return V2V metrics', () => {
      return request(app.getHttpServer())
        .get('/admin/v2v/metrics')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('totalConnections');
          expect(res.body).toHaveProperty('activeConnections');
          expect(res.body).toHaveProperty('activeSessions');
        });
    });
  });
});
