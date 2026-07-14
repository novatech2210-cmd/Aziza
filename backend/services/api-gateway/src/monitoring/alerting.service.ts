import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { MetricsService } from './metrics.service';
import { ErrorAggregationService } from './error-aggregation.service';
import { HealthCheckService } from './health-check.service';

export interface Alert {
  id: string;
  level: 'info' | 'warning' | 'critical';
  service: string;
  message: string;
  timestamp: Date;
  resolved: boolean;
  metadata?: Record<string, any>;
}

export interface AlertRule {
  name: string;
  condition: (metrics: any) => boolean;
  level: 'warning' | 'critical' | 'info';
  message: string;
  service: string;
  cooldownMs: number;
}

@Injectable()
export class AlertingService {
  private readonly logger = new Logger(AlertingService.name);
  private alerts: Alert[] = [];
  private lastAlertTimes: Map<string, number> = new Map();
  private readonly MAX_ALERTS = 1000;

  constructor(
    private metricsService: MetricsService,
    private errorService: ErrorAggregationService,
    private healthService: HealthCheckService,
  ) {}

  private readonly rules: AlertRule[] = [
    {
      name: 'high_error_rate',
      condition: (m) => m.error_rate > 10,
      level: 'critical',
      message: 'Error rate exceeds 10%',
      service: 'gateway',
      cooldownMs: 300000, // 5 minutes
    },
    {
      name: 'high_ttft_p95',
      condition: (m) => m.ttft?.p95 > 3000,
      level: 'warning',
      message: 'P95 TTFT exceeds 3 seconds',
      service: 'gateway',
      cooldownMs: 600000, // 10 minutes
    },
    {
      name: 'low_success_rate',
      condition: (m) => m.success_rate < 90,
      level: 'critical',
      message: 'Success rate below 90%',
      service: 'gateway',
      cooldownMs: 300000,
    },
    {
      name: 'gpu_overheating',
      condition: (m) => m.gpu_temp > 85,
      level: 'critical',
      message: 'GPU temperature exceeds 85°C',
      service: 'gpu',
      cooldownMs: 120000, // 2 minutes
    },
    {
      name: 'gpu_high_memory',
      condition: (m) => m.gpu_mem_used / m.gpu_mem_total > 0.95,
      level: 'warning',
      message: 'GPU memory usage exceeds 95%',
      service: 'gpu',
      cooldownMs: 600000,
    },
    {
      name: 'high_request_rate',
      condition: (m) => m.requests_last_minute > 100,
      level: 'info',
      message: 'High request rate detected',
      service: 'gateway',
      cooldownMs: 900000, // 15 minutes
    },
  ];

  @Cron(CronExpression.EVERY_30_SECONDS)
  async evaluateRules() {
    try {
      const metrics = this.metricsService.getMetricsSummary();
      const gpuData = await this.getGpuMetricsForAlerts();

      const combinedMetrics = {
        ...metrics,
        ...gpuData,
      };

      for (const rule of this.rules) {
        if (rule.condition(combinedMetrics)) {
          this.createAlert(rule, combinedMetrics);
        }
      }
    } catch (error) {
      this.logger.error(`Alert evaluation failed: ${error.message}`);
    }
  }

  private createAlert = async (rule: AlertRule, metrics: any) => {
    const now = Date.now();
    const lastAlert = this.lastAlertTimes.get(rule.name) || 0;

    // Cooldown check
    if (now - lastAlert < rule.cooldownMs) {
      return;
    }

    const alert: Alert = {
      id: `alert_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      level: rule.level,
      service: rule.service,
      message: rule.message,
      timestamp: new Date(),
      resolved: false,
      metadata: {
        rule: rule.name,
        metrics: this.sanitizeMetrics(metrics),
      },
    };

    this.alerts.unshift(alert);
    if (this.alerts.length > this.MAX_ALERTS) {
      this.alerts.pop();
    }

    this.lastAlertTimes.set(rule.name, now);

    this.logger.warn(
      `ALERT [${rule.level.toUpperCase()}] ${rule.service}: ${rule.message}`,
    );

    // Persist to error aggregation service
    await this.errorService.logWarning(
      rule.service,
      `[ALERT] ${rule.message}`,
      { alertId: alert.id, rule: rule.name, level: rule.level },
    );
  }

  private sanitizeMetrics(metrics: any) {
    // Remove sensitive or noisy data
    const sanitized = { ...metrics };
    delete sanitized.total_requests;
    delete sanitized.total_errors;
    return sanitized;
  }

  private async getGpuMetricsForAlerts() {
    try {
      // Try to get GPU metrics from nvidia-smi
      const { execSync } = require('child_process');
      const output = execSync(
        'nvidia-smi --query-gpu=temperature.gpu,memory.used,memory.total --format=csv,noheader,nounits',
        { timeout: 5000 }
      ).toString().trim();
      
      const [temp, memUsed, memTotal] = output.split(',').map(Number);
      return {
        gpu_temp: temp,
        gpu_mem_used: memUsed,
        gpu_mem_total: memTotal,
      };
    } catch {
      return { gpu_temp: 0, gpu_mem_used: 0, gpu_mem_total: 0 };
    }
  }

  getAlerts(options?: { level?: string; service?: string; limit?: number }) {
    let filtered = this.alerts;

    if (options?.level) {
      filtered = filtered.filter(a => a.level === options.level);
    }
    if (options?.service) {
      filtered = filtered.filter(a => a.service === options.service);
    }

    return filtered.slice(0, options?.limit || 100);
  }

  getAlertStats() {
    const now = Date.now();
    const lastHour = now - 3600000;
    const lastDay = now - 86400000;

    const hourly = this.alerts.filter(a => a.timestamp.getTime() > lastHour);
    const daily = this.alerts.filter(a => a.timestamp.getTime() > lastDay);

    return {
      total: this.alerts.length,
      unresolved: this.alerts.filter(a => !a.resolved).length,
      hourly: {
        total: hourly.length,
        critical: hourly.filter(a => a.level === 'critical').length,
        warning: hourly.filter(a => a.level === 'warning').length,
        info: hourly.filter(a => a.level === 'info').length,
      },
      daily: {
        total: daily.length,
        critical: daily.filter(a => a.level === 'critical').length,
        warning: daily.filter(a => a.level === 'warning').length,
        info: daily.filter(a => a.level === 'info').length,
      },
      by_service: this.groupAlertsByService(),
    };
  }

  private groupAlertsByService() {
    const grouped: Record<string, number> = {};
    for (const alert of this.alerts) {
      grouped[alert.service] = (grouped[alert.service] || 0) + 1;
    }
    return grouped;
  }

  resolveAlert(alertId: string) {
    const alert = this.alerts.find(a => a.id === alertId);
    if (alert) {
      alert.resolved = true;
      return { success: true, alertId };
    }
    return { success: false, alertId, error: 'Alert not found' };
  }

  clearResolvedAlerts() {
    const before = this.alerts.length;
    this.alerts = this.alerts.filter(a => !a.resolved);
    return { cleared: before - this.alerts.length };
  }
}
