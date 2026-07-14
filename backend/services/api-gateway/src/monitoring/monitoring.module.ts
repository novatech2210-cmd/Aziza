import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { ScheduleModule } from '@nestjs/schedule';
import { GpuMetricsService } from './gpu-metrics.service';
import { MetricsService } from './metrics.service';
import { ErrorAggregationService } from './error-aggregation.service';
import { HealthCheckService } from './health-check.service';
import { StructuredLoggingService } from './structured-logging.service';
import { AlertingService } from './alerting.service';
import { CostTrackingService } from './cost-tracking.service';
import { SLAMonitoringService } from './sla-monitoring.service';
import { LogCollectorService } from './log-collector.service';
import { ErrorLog, ErrorLogSchema } from './error-aggregation.service';
import { HealthCheck, HealthCheckSchema } from './health-check.service';
import { StructuredLog, StructuredLogSchema } from './structured-logging.service';

@Module({
  imports: [
    MongooseModule.forFeature([
      { name: ErrorLog.name, schema: ErrorLogSchema },
      { name: HealthCheck.name, schema: HealthCheckSchema },
      { name: StructuredLog.name, schema: StructuredLogSchema },
    ]),
    ScheduleModule.forRoot(),
  ],
  providers: [
    GpuMetricsService,
    MetricsService,
    ErrorAggregationService,
    HealthCheckService,
    StructuredLoggingService,
    AlertingService,
    CostTrackingService,
    SLAMonitoringService,
    LogCollectorService,
  ],
  exports: [
    GpuMetricsService,
    MetricsService,
    ErrorAggregationService,
    HealthCheckService,
    StructuredLoggingService,
    AlertingService,
    CostTrackingService,
    SLAMonitoringService,
    LogCollectorService,
  ],
})
export class MonitoringModule {}
