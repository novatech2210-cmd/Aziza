import { Injectable, Logger } from '@nestjs/common';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface GpuInfo {
  index: number;
  name: string;
  memoryTotal: number;
  memoryUsed: number;
  memoryFree: number;
  utilizationGpu: number;
  utilizationMemory: number;
  temperature: number;
  powerDraw: number;
  powerLimit: number;
}

@Injectable()
export class GpuMetricsService {
  private readonly logger = new Logger(GpuMetricsService.name);
  private cachedMetrics: GpuInfo[] = [];
  private lastFetch = 0;
  private readonly CACHE_TTL = 2000; // 2 seconds

  async getGpuMetrics(): Promise<GpuInfo[]> {
    const now = Date.now();
    if (now - this.lastFetch < this.CACHE_TTL && this.cachedMetrics.length > 0) {
      return this.cachedMetrics;
    }

    try {
      const { stdout } = await execAsync(
        'nvidia-smi --query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu,utilization.memory,temperature.gpu,power.draw,power.limit --format=csv,noheader,nounits',
        { timeout: 5000 }
      );

      this.cachedMetrics = stdout
        .trim()
        .split('\n')
        .filter(line => line.trim())
        .map(line => {
          const parts = line.split(',').map(s => s.trim());
          return {
            index: parseInt(parts[0], 10),
            name: parts[1],
            memoryTotal: parseInt(parts[2], 10),
            memoryUsed: parseInt(parts[3], 10),
            memoryFree: parseInt(parts[4], 10),
            utilizationGpu: parseInt(parts[5], 10),
            utilizationMemory: parseInt(parts[6], 10),
            temperature: parseInt(parts[7], 10),
            powerDraw: parseFloat(parts[8]),
            powerLimit: parseFloat(parts[9]),
          };
        });

      this.lastFetch = now;
      return this.cachedMetrics;
    } catch (error) {
      this.logger.error(`Failed to get GPU metrics: ${error.message}`);
      return this.cachedMetrics.length > 0 ? this.cachedMetrics : [];
    }
  }

  async getGpuSummary() {
    const gpus = await this.getGpuMetrics();
    if (gpus.length === 0) {
      return { available: false, gpus: [] };
    }

    return {
      available: true,
      count: gpus.length,
      gpus: gpus.map(gpu => ({
        index: gpu.index,
        name: gpu.name,
        memory: {
          total: gpu.memoryTotal,
          used: gpu.memoryUsed,
          free: gpu.memoryFree,
          percentUsed: Math.round((gpu.memoryUsed / gpu.memoryTotal) * 100),
        },
        utilization: gpu.utilizationGpu,
        temperature: gpu.temperature,
        power: {
          draw: gpu.powerDraw,
          limit: gpu.powerLimit,
          percentUsed: Math.round((gpu.powerDraw / gpu.powerLimit) * 100),
        },
      })),
    };
  }
}
