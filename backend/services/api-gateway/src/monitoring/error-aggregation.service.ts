import { Injectable, Logger } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

export type ErrorLogDocument = ErrorLog & Document;

@Schema({ timestamps: true, capped: { size: 10485760, max: 10000 } }) // 10MB, max 10k docs
export class ErrorLog {
  @Prop({ required: true })
  service: string;

  @Prop({ required: true })
  level: string;

  @Prop({ required: true })
  message: string;

  @Prop()
  stack: string;

  @Prop({ type: Object })
  metadata: Record<string, any>;

  @Prop({ default: false })
  resolved: boolean;
}

export const ErrorLogSchema = SchemaFactory.createForClass(ErrorLog);
ErrorLogSchema.index({ service: 1, createdAt: -1 });
ErrorLogSchema.index({ level: 1 });
ErrorLogSchema.index({ resolved: 1 });

@Injectable()
export class ErrorAggregationService {
  private readonly logger = new Logger(ErrorAggregationService.name);

  constructor(
    @InjectModel(ErrorLog.name) private errorModel: Model<ErrorLogDocument>,
  ) {}

  async logError(service: string, message: string, stack?: string, metadata?: Record<string, any>) {
    try {
      await this.errorModel.create({
        service,
        level: 'error',
        message,
        stack,
        metadata,
      });
    } catch (error) {
      this.logger.error(`Failed to log error: ${error.message}`);
    }
  }

  async logWarning(service: string, message: string, metadata?: Record<string, any>) {
    try {
      await this.errorModel.create({
        service,
        level: 'warning',
        message,
        metadata,
      });
    } catch (error) {
      this.logger.error(`Failed to log warning: ${error.message}`);
    }
  }

  async getRecentErrors(limit = 50, service?: string) {
    const query: any = {};
    if (service) query.service = service;

    return this.errorModel
      .find(query)
      .sort({ createdAt: -1 })
      .limit(limit)
      .select('-__v')
      .exec();
  }

  async getErrorStats() {
    const now = new Date();
    const lastHour = new Date(now.getTime() - 60 * 60 * 1000);
    const lastDay = new Date(now.getTime() - 24 * 60 * 60 * 1000);

    const [hourlyByService, dailyByService, totalUnresolved] = await Promise.all([
      this.errorModel.aggregate([
        { $match: { createdAt: { $gte: lastHour } } },
        { $group: { _id: '$service', count: { $sum: 1 } } },
        { $sort: { count: -1 } },
      ]),
      this.errorModel.aggregate([
        { $match: { createdAt: { $gte: lastDay } } },
        { $group: { _id: '$service', count: { $sum: 1 } } },
        { $sort: { count: -1 } },
      ]),
      this.errorModel.countDocuments({ resolved: false }),
    ]);

    return {
      hourly_by_service: hourlyByService.map(s => ({ service: s._id, count: s.count })),
      daily_by_service: dailyByService.map(s => ({ service: s._id, count: s.count })),
      total_unresolved: totalUnresolved,
    };
  }

  async markResolved(errorId: string) {
    return this.errorModel.findByIdAndUpdate(errorId, { resolved: true }).exec();
  }
}
