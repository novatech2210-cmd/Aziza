import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { MetricsService } from './metrics.service';
import { HealthCheckService, HealthStatus } from './health-check.service';

export interface SLATarget {
  name: string;
  metric: string;
  target: number;
  unit: string;
  window: 'hour' | 'day' | 'week';
}

export interface SLAResult {
  target: SLATarget;
  current: number;
  achieved: boolean;
  budget: number; // Allowed downtime/errors in window
  consumed: number; // Actual downtime/errors in window
  remaining: number;
}

export interface SLAReport {
  timestamp: Date;
  targets: SLAResult[];
  overallScore: number; // 0-100
  uptime: number; // percentage
  avgLatency: number; // ms
  p99Latency: number; // ms
  errorBudget: {
    total: number;
    consumed: number;
    remaining: number;
  };
}

@Injectable()
export class SLAMonitoringService {
  private readonly logger = new Logger(SLAMonitoringService.name);
  private reports: SLAReport[] = [];
  private readonly MAX_REPORTS = 1008; // 7 days at 10-minute intervals

  private readonly targets: SLATarget[] = [
    {
      name: 'Availability',
      metric: 'success_rate',
      target: 99.9,
      unit: '%',
      window: 'day',
    },
    {
      name: 'Latency P95',
      metric: 'ttft_p95',
      target: 2000,
      unit: 'ms',
      window: 'hour',
    },
    {
      name: 'Latency P99',
      metric: 'ttft_p99',
      target: 5000,
      unit: 'ms',
      window: 'hour',
    },
    {
      name: 'Error Rate',
      metric: 'error_rate',
      target: 1.0,
      unit: '%',
      window: 'day',
    },
    {
      name: 'Throughput',
      metric: 'requests_per_minute',
      target: 10,
      unit: 'req/min',
      window: 'hour',
    },
  ];

  constructor(
    private metricsService: MetricsService,
    private healthService: HealthCheckService,
  ) {}

  @Cron(CronExpression.EVERY_10_MINUTES)
  async generateReport() {
    try {
      const metrics = this.metricsService.getMetricsSummary();
      const results = this.targets.map(target => this.evaluateTarget(target, metrics));

      // Calculate overall score (weighted average)
      const weights = [0.3, 0.25, 0.2, 0.15, 0.1]; // Availability, P95, P99, Error Rate, Throughput
      let overallScore = 0;
      for (let i = 0; i < results.length; i++) {
        const score = results[i].achieved ? 100 : (results[i].current / results[i].target.target) * 100;
        overallScore += score * (weights[i] || 0.1);
      }

      // Calculate uptime (from health checks)
      const uptime = await this.calculateUptime();

      const report: SLAReport = {
        timestamp: new Date(),
        targets: results,
        overallScore: Math.min(100, Math.max(0, overallScore)),
        uptime,
        avgLatency: metrics.ttft?.avg || 0,
        p99Latency: metrics.ttft?.p99 || 0,
        errorBudget: this.calculateErrorBudget(metrics),
      };

      this.reports.push(report);
      if (this.reports.length > this.MAX_REPORTS) {
        this.reports.shift();
      }

      // Log SLA breaches
      for (const result of results) {
        if (!result.achieved) {
          this.logger.warn(
            `SLA breach: ${result.target.name} = ${result.current}${result.target.unit} (target: ${result.target.target}${result.target.unit})`,
          );
        }
      }
    } catch (error) {
      this.logger.error(`SLA report generation failed: ${error.message}`);
    }
  }

  private evaluateTarget(target: SLATarget, metrics: any): SLAResult {
    let current = 0;
    
    switch (target.metric) {
      case 'success_rate':
        current = metrics.success_rate || 100;
        break;
      case 'ttft_p95':
        current = metrics.ttft?.p95 || 0;
        break;
      case 'ttft_p99':
        current = metrics.ttft?.p99 || 0;
        break;
      case 'error_rate':
        current = metrics.error_rate || 0;
        break;
      case 'requests_per_minute':
        current = metrics.requests_last_minute || 0;
        break;
      default:
        current = 0;
    }

    // For latency and error rate, lower is better
    const isLowerBetter = ['ttft_p95', 'ttft_p99', 'error_rate'].includes(target.metric);
    const achieved = isLowerBetter ? current <= target.target : current >= target.target;

    // Calculate error budget (simplified)
    const windowMs = target.window === 'hour' ? 3600000 : target.window === 'day' ? 86400000 : 604800000;
    const budget = target.target;
    const consumed = isLowerBetter ? (current / target.target) * 100 : ((100 - current) / (100 - target.target)) * 100;

    return {
      target,
      current,
      achieved,
      budget,
      consumed: Math.min(100, consumed),
      remaining: Math.max(0, 100 - consumed),
    };
  }

  private async calculateUptime(): Promise<number> {
    try {
      const healthStatuses = await this.healthService.getAllServiceHealth();
      if (healthStatuses.length === 0) return 100;

      const healthyCount = healthStatuses.filter(h => h.status === 'healthy').length;
      return (healthyCount / healthStatuses.length) * 100;
    } catch {
      return 100;
    }
  }

  private calculateErrorBudget(metrics: any) {
    const totalBudget = 100; // 100% budget
    const consumed = metrics.error_rate || 0;
    return {
      total: totalBudget,
      consumed,
      remaining: totalBudget - consumed,
    };
  }

  getCurrentSLA() {
    if (this.reports.length === 0) {
      return {
        status: 'no_data',
        message: 'No SLA data available yet',
      };
    }

    const latest = this.reports[this.reports.length - 1];
    return {
      status: latest.overallScore >= 99 ? 'healthy' : latest.overallScore >= 95 ? 'degraded' : 'unhealthy',
      score: latest.overallScore,
      uptime: latest.uptime,
      avgLatency: latest.avgLatency,
      p99Latency: latest.p99Latency,
      errorBudget: latest.errorBudget,
      targets: latest.targets,
      lastReport: latest.timestamp,
    };
  }

  getSLATrend(options: { hours?: number }) {
    const hours = options.hours || 24;
    const cutoff = Date.now() - hours * 3600000;
    const relevant = this.reports.filter(r => r.timestamp.getTime() > cutoff);

    return {
      reports: relevant,
      averageScore: relevant.length > 0
        ? relevant.reduce((sum, r) => sum + r.overallScore, 0) / relevant.length
        : 0,
      minScore: relevant.length > 0
        ? Math.min(...relevant.map(r => r.overallScore))
        : 0,
      breaches: relevant.filter(r => r.overallScore < 99).length,
    };
  }
}
