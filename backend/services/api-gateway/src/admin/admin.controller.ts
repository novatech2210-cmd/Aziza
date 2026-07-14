import {
  Controller,
  Get,
  Delete,
  Param,
  Post,
  Body,
  Query,
  UseGuards,
} from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { RolesGuard } from '../auth/guards/roles.guard';
import { Roles } from '../auth/roles.decorator';
import { GpuMetricsService } from '../monitoring/gpu-metrics.service';
import { MetricsService } from '../monitoring/metrics.service';
import { ErrorAggregationService } from '../monitoring/error-aggregation.service';
import { HealthCheckService } from '../monitoring/health-check.service';
import { StructuredLoggingService } from '../monitoring/structured-logging.service';
import { AlertingService } from '../monitoring/alerting.service';
import { CostTrackingService } from '../monitoring/cost-tracking.service';
import { SLAMonitoringService } from '../monitoring/sla-monitoring.service';
import { V2VGateway } from '../gateway/v2v.gateway';

@Controller('admin')
@UseGuards(JwtAuthGuard, RolesGuard)
@Roles('admin')
export class AdminController {
  constructor(
    private gpuMetrics: GpuMetricsService,
    private metricsService: MetricsService,
    private errorService: ErrorAggregationService,
    private healthService: HealthCheckService,
    private loggingService: StructuredLoggingService,
    private alertingService: AlertingService,
    private costService: CostTrackingService,
    private slaService: SLAMonitoringService,
    private v2vGateway: V2VGateway,
  ) {}

  // ── Sessions ─────────────────────────────────────────────────────────────

  @Get('sessions')
  getSessions() {
    return [];
  }

  @Delete('sessions')
  deleteAllSessions() {
    return { deleted: 0 };
  }

  @Delete('sessions/:id')
  deleteSession(@Param('id') id: string) {
    return { success: true, id };
  }

  // ── GPU Metrics ──────────────────────────────────────────────────────────

  @Get('gpu')
  async getGpuMetrics() {
    return this.gpuMetrics.getGpuSummary();
  }

  // ── Request Metrics ──────────────────────────────────────────────────────

  @Get('metrics')
  getMetrics() {
    return this.metricsService.getMetricsSummary();
  }

  @Get('latency/heatmap')
  getLatencyHeatmap() {
    return this.metricsService.getLatencyHeatmap();
  }

  // ── Errors ────────────────────────────────────────────────────────────────

  @Get('errors')
  async getErrors(
    @Query('limit') limit?: string,
    @Query('service') service?: string,
  ) {
    return this.errorService.getRecentErrors(
      limit ? parseInt(limit) : 50,
      service,
    );
  }

  @Get('errors/stats')
  async getErrorStats() {
    return this.errorService.getErrorStats();
  }

  @Post('errors/:id/resolve')
  async resolveError(@Param('id') id: string) {
    return this.errorService.markResolved(id);
  }

  // ── Health Checks ────────────────────────────────────────────────────────

  @Get('health')
  async getAllHealth() {
    return this.healthService.getAllServiceHealth();
  }

  @Get('health/:service')
  async getServiceHealth(@Param('service') service: string) {
    return this.healthService.getServiceHealth(service);
  }

  // ── RAG ───────────────────────────────────────────────────────────────────

  @Get('rag/stats')
  getRagStats() {
    return { doc_count: 0, index_size_bytes: 0, last_updated: null };
  }

  @Post('rag/ingest')
  ragIngest(@Body() body: { texts?: string[] }) {
    return { ingested: 0, ids: [] };
  }

  @Delete('rag/clear')
  ragClear() {
    return { cleared: 0 };
  }

  // ── V2V Metrics ─────────────────────────────────────────────────────────

  @Get('v2v/metrics')
  getV2VMetrics() {
    return this.v2vGateway.getMetrics();
  }

  // ── Structured Logging ───────────────────────────────────────────────────

  @Get('logs')
  async getLogs(
    @Query('limit') limit?: string,
    @Query('service') service?: string,
    @Query('level') level?: string,
    @Query('correlationId') correlationId?: string,
    @Query('sessionId') sessionId?: string,
  ) {
    return this.loggingService.getLogs({
      limit: limit ? parseInt(limit) : 100,
      service,
      level,
      correlationId,
      sessionId,
    });
  }

  @Get('logs/stats')
  async getLogStats() {
    return this.loggingService.getLogStats({});
  }

  // ── Alerting ─────────────────────────────────────────────────────────────

  @Get('alerts')
  getAlerts(
    @Query('level') level?: string,
    @Query('service') service?: string,
    @Query('limit') limit?: string,
  ) {
    return this.alertingService.getAlerts({
      level,
      service,
      limit: limit ? parseInt(limit) : 100,
    });
  }

  @Get('alerts/stats')
  getAlertStats() {
    return this.alertingService.getAlertStats();
  }

  @Post('alerts/:id/resolve')
  resolveAlert(@Param('id') id: string) {
    return this.alertingService.resolveAlert(id);
  }

  @Delete('alerts/resolved')
  clearResolvedAlerts() {
    return this.alertingService.clearResolvedAlerts();
  }

  // ── Cost Tracking ────────────────────────────────────────────────────────

  @Get('costs')
  getCosts() {
    return this.costService.getCostSummary();
  }

  @Get('costs/trend')
  getCostTrend(@Query('hours') hours?: string) {
    return this.costService.getCostTrend({
      hours: hours ? parseInt(hours) : 24,
    });
  }

  @Get('costs/rate')
  getCurrentCostRate() {
    return { rate_usd_per_hour: this.costService.getCurrentCostRate() };
  }

  // ── SLA Monitoring ───────────────────────────────────────────────────────

  @Get('sla')
  getCurrentSLA() {
    return this.slaService.getCurrentSLA();
  }

  @Get('sla/trend')
  getSLATrend(@Query('hours') hours?: string) {
    return this.slaService.getSLATrend({
      hours: hours ? parseInt(hours) : 24,
    });
  }
}
