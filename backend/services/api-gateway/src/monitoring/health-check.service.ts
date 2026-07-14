import { Injectable, Logger } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

export type HealthCheckDocument = HealthCheck & Document;

@Schema({ timestamps: true })
export class HealthCheck {
  @Prop({ required: true })
  service: string;

  @Prop({ required: true, enum: ['healthy', 'degraded', 'unhealthy'] })
  status: string;

  @Prop({ type: Object })
  checks: Record<string, { status: string; message?: string; latencyMs?: number }>;

  @Prop()
  lastChecked: Date;
}

export const HealthCheckSchema = SchemaFactory.createForClass(HealthCheck);
HealthCheckSchema.index({ service: 1 }, { unique: true });

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  service: string;
  timestamp: string;
  checks: Record<string, { status: string; message?: string; latencyMs?: number }>;
  uptime?: number;
}

@Injectable()
export class HealthCheckService {
  private readonly logger = new Logger(HealthCheckService.name);
  private readonly serviceStartTimes: Map<string, number> = new Map();

  constructor(
    @InjectModel(HealthCheck.name) private healthModel: Model<HealthCheckDocument>,
  ) {}

  registerService(serviceName: string) {
    this.serviceStartTimes.set(serviceName, Date.now());
  }

  async checkService(serviceName: string, checks: Record<string, { status: string; message?: string; latencyMs?: number }>): Promise<HealthStatus> {
    const overallStatus = this.determineOverallStatus(checks);
    const startTime = this.serviceStartTimes.get(serviceName);
    const uptime = startTime ? Math.floor((Date.now() - startTime) / 1000) : undefined;

    const healthStatus: HealthStatus = {
      status: overallStatus,
      service: serviceName,
      timestamp: new Date().toISOString(),
      checks,
      uptime,
    };

    // Persist to MongoDB
    try {
      await this.healthModel.findOneAndUpdate(
        { service: serviceName },
        { ...healthStatus, lastChecked: new Date() },
        { upsert: true, new: true },
      );
    } catch (error) {
      this.logger.error(`Failed to persist health check: ${error.message}`);
    }

    return healthStatus;
  }

  async getServiceHealth(serviceName: string): Promise<HealthStatus | null> {
    const doc = await this.healthModel.findOne({ service: serviceName }).exec();
    if (!doc) return null;

    const startTime = this.serviceStartTimes.get(serviceName);
    return {
      status: doc.status as any,
      service: doc.service,
      timestamp: doc.lastChecked?.toISOString() || new Date().toISOString(),
      checks: doc.checks || {},
      uptime: startTime ? Math.floor((Date.now() - startTime) / 1000) : undefined,
    };
  }

  async getAllServiceHealth() {
    const services = await this.healthModel.find().exec();
    return services.map(doc => ({
      service: doc.service,
      status: doc.status,
      lastChecked: doc.lastChecked,
      checks: doc.checks,
    }));
  }

  private determineOverallStatus(checks: Record<string, { status: string }>): 'healthy' | 'degraded' | 'unhealthy' {
    const statuses = Object.values(checks).map(c => c.status);
    if (statuses.includes('unhealthy')) return 'unhealthy';
    if (statuses.includes('degraded')) return 'degraded';
    return 'healthy';
  }
}
