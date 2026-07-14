import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { MetricsService } from './metrics.service';
import { GpuMetricsService } from './gpu-metrics.service';

export interface CostRecord {
  timestamp: Date;
  gpuSeconds: number;
  gpuCostUsd: number;
  inferenceTokens: number;
  inferenceCostUsd: number;
  totalCostUsd: number;
  metadata: Record<string, any>;
}

export interface CostSummary {
  hourly: CostRecord[];
  daily: CostRecord[];
  totalCostUsd: number;
  estimatedMonthlyUsd: number;
  gpuUtilization: number;
  costPerInference: number;
}

@Injectable()
export class CostTrackingService {
  private readonly logger = new Logger(CostTrackingService.name);
  private costHistory: CostRecord[] = [];
  private readonly MAX_HISTORY = 1440; // 24 hours at 1-minute intervals

  // GPU pricing (NVIDIA A6000 on-demand)
  private readonly GPU_COST_PER_HOUR = 1.50; // ~$1.50/hr for A6000
  private readonly GPU_IDLE_COST_PER_HOUR = 0.30; // Idle power draw

  // Token pricing (self-hosted vLLM - only power cost)
  private readonly TOKEN_COST_PER_1K = 0.0001; // Very low for self-hosted

  constructor(
    private metricsService: MetricsService,
    private gpuMetrics: GpuMetricsService,
  ) {}

  @Cron(CronExpression.EVERY_MINUTE)
  async trackCosts() {
    try {
      const metrics = this.metricsService.getMetricsSummary();
      const gpuInfoArray = await this.gpuMetrics.getGpuMetrics();
      const gpuInfo = gpuInfoArray?.[0];

      // Calculate GPU cost
      const gpuUtilization = gpuInfo?.utilizationGpu || 0;
      const gpuSeconds = 60; // 1-minute interval
      const activeGpuFraction = gpuUtilization / 100;
      const gpuCost = ((this.GPU_COST_PER_HOUR * activeGpuFraction) + 
                       (this.GPU_IDLE_COST_PER_HOUR * (1 - activeGpuFraction))) / 60;

      // Calculate inference cost (tokens processed)
      const inferenceTokens = metrics.requests_last_minute * (metrics.tokens_per_sec?.avg || 0) * 60;
      const inferenceCost = (inferenceTokens / 1000) * this.TOKEN_COST_PER_1K;

      const record: CostRecord = {
        timestamp: new Date(),
        gpuSeconds,
        gpuCostUsd: gpuCost,
        inferenceTokens,
        inferenceCostUsd: inferenceCost,
        totalCostUsd: gpuCost + inferenceCost,
        metadata: {
          gpuUtilization,
          requestsPerMinute: metrics.requests_last_minute,
          avgTokensPerSec: metrics.tokens_per_sec?.avg || 0,
          gpuTemp: gpuInfo?.temperature || 0,
        },
      };

      this.costHistory.push(record);
      if (this.costHistory.length > this.MAX_HISTORY) {
        this.costHistory.shift();
      }
    } catch (error) {
      this.logger.error(`Cost tracking failed: ${error.message}`);
    }
  }

  getCostSummary(): CostSummary {
    const now = Date.now();
    const lastHour = now - 3600000;
    const lastDay = now - 86400000;

    const hourly = this.costHistory.filter(r => r.timestamp.getTime() > lastHour);
    const daily = this.costHistory.filter(r => r.timestamp.getTime() > lastDay);

    const totalCost = this.costHistory.reduce((sum, r) => sum + r.totalCostUsd, 0);
    const dailyCost = daily.reduce((sum, r) => sum + r.totalCostUsd, 0);
    const estimatedMonthly = dailyCost * 30;

    const totalInferences = this.costHistory.length;
    const costPerInference = totalInferences > 0 ? totalCost / totalInferences : 0;

    const avgGpuUtil = this.costHistory.length > 0
      ? this.costHistory.reduce((sum, r) => sum + (r.metadata.gpuUtilization || 0), 0) / this.costHistory.length
      : 0;

    return {
      hourly: hourly.slice(-60), // Last hour, per-minute
      daily: daily.slice(-1440), // Last day, per-minute
      totalCostUsd: totalCost,
      estimatedMonthlyUsd: estimatedMonthly,
      gpuUtilization: avgGpuUtil,
      costPerInference,
    };
  }

  getCostTrend(options: { hours?: number }) {
    const hours = options.hours || 24;
    const cutoff = Date.now() - hours * 3600000;
    const relevant = this.costHistory.filter(r => r.timestamp.getTime() > cutoff);

    // Group by hour
    const hourlyCosts: Record<string, number> = {};
    for (const record of relevant) {
      const hourKey = record.timestamp.toISOString().slice(0, 13);
      hourlyCosts[hourKey] = (hourlyCosts[hourKey] || 0) + record.totalCostUsd;
    }

    return {
      hourly: Object.entries(hourlyCosts).map(([hour, cost]) => ({ hour, cost })),
      totalHours: hours,
      totalCost: relevant.reduce((sum, r) => sum + r.totalCostUsd, 0),
    };
  }

  // Get current cost rate (USD per hour)
  getCurrentCostRate(): number {
    if (this.costHistory.length === 0) return 0;
    
    const last10 = this.costHistory.slice(-10);
    const avgCostPerMinute = last10.reduce((sum, r) => sum + r.totalCostUsd, 0) / last10.length;
    return avgCostPerMinute * 60; // Convert to hourly
  }
}
