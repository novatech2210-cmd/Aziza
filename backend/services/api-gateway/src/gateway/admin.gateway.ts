import {
  WebSocketGateway,
  WebSocketServer,
  OnGatewayConnection,
  OnGatewayDisconnect,
} from '@nestjs/websockets';
import { Server } from 'ws';
import { Logger } from '@nestjs/common';
import * as jwt from 'jsonwebtoken';
import { GpuMetricsService } from '../monitoring/gpu-metrics.service';
import { MetricsService } from '../monitoring/metrics.service';

const JWT_SECRET = process.env.JWT_SECRET;
if (!JWT_SECRET) {
  throw new Error('JWT_SECRET environment variable is required');
}

@WebSocketGateway({ 
  path: '/api/admin-stats',
  cors: { origin: '*' }
})
export class AdminGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;

  private readonly logger = new Logger(AdminGateway.name);
  private statsIntervals: Map<string, NodeJS.Timeout> = new Map();

  constructor(
    private gpuMetrics: GpuMetricsService,
    private metricsService: MetricsService,
  ) {}

  handleConnection(client: any, request: any) {
    // Authenticate admin via JWT token
    const url = new URL(request.url || '', 'http://localhost');
    const token = url.searchParams.get('token');
    if (!token) {
      this.logger.warn('Admin connection rejected: no token');
      client.close(4001, 'Authentication required');
      return;
    }

    try {
      const payload = jwt.verify(token, JWT_SECRET, { algorithms: ['HS256'] }) as jwt.JwtPayload;
      if (payload.role !== 'admin') {
        this.logger.warn(`Admin connection rejected: not admin (role=${payload.role})`);
        client.close(4003, 'Admin access required');
        return;
      }
      client.userId = payload.sub || payload.userId;
      client.username = payload.username;
    } catch (err) {
      this.logger.warn(`Admin connection rejected: invalid token - ${err.message}`);
      client.close(4002, 'Invalid token');
      return;
    }

    const clientId = Math.random().toString(36).slice(2);
    this.logger.log(`Admin client connected: ${clientId} (user: ${client.username || client.userId})`);
    
    // Send real periodic stats
    const interval = setInterval(async () => {
      if (client.readyState === 1) {
        try {
          const [gpuSummary, metrics] = await Promise.all([
            this.gpuMetrics.getGpuSummary(),
            this.metricsService.getMetricsSummary(),
          ]);

          const gpu0 = gpuSummary.gpus?.[0];
          
          client.send(JSON.stringify({
            active_sessions: metrics.requests_last_minute,
            gpu_0_util: gpu0?.utilization || 0,
            gpu_0_mem: gpu0?.memory?.used || 0,
            gpu_0_mem_total: gpu0?.memory?.total || 0,
            gpu_0_temp: gpu0?.temperature || 0,
            gpu_0_power: gpu0?.power?.draw || 0,
            latency_p50: metrics.ttft?.p50 || 0,
            latency_p95: metrics.ttft?.p95 || 0,
            latency_p99: metrics.ttft?.p99 || 0,
            requests_total: metrics.total_requests,
            error_rate: metrics.error_rate,
            success_rate: metrics.success_rate,
            tokens_per_sec: metrics.tokens_per_sec?.avg || 0,
          }));
        } catch (error) {
          this.logger.error(`Failed to send stats: ${error.message}`);
        }
      }
    }, 2000);

    this.statsIntervals.set(clientId, interval);
  }

  handleDisconnect(client: any) {
    // Clean up all intervals for this client
    for (const [id, interval] of this.statsIntervals.entries()) {
      clearInterval(interval);
      this.statsIntervals.delete(id);
    }
    this.logger.log('Admin client disconnected');
  }
}
