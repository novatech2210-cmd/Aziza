import { Injectable, Logger } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

export type StructuredLogDocument = StructuredLog & Document;

@Schema({ timestamps: true, capped: { size: 52428800, max: 50000 } }) // 50MB, max 50k docs
export class StructuredLog {
  @Prop({ required: true })
  level: string;

  @Prop({ required: true })
  service: string;

  @Prop({ required: true })
  message: string;

  @Prop()
  correlationId: string;

  @Prop()
  sessionId: string;

  @Prop()
  userId: string;

  @Prop({ type: Object })
  metadata: Record<string, any>;

  @Prop()
  stack: string;

  @Prop()
  requestId: string;
}

export const StructuredLogSchema = SchemaFactory.createForClass(StructuredLog);
StructuredLogSchema.index({ correlationId: 1 });
StructuredLogSchema.index({ service: 1, createdAt: -1 });
StructuredLogSchema.index({ level: 1, createdAt: -1 });
StructuredLogSchema.index({ sessionId: 1 });

export interface LogContext {
  correlationId?: string;
  sessionId?: string;
  userId?: string;
  requestId?: string;
  [key: string]: any;
}

@Injectable()
export class StructuredLoggingService {
  private readonly logger = new Logger(StructuredLoggingService.name);

  constructor(
    @InjectModel(StructuredLog.name) private logModel: Model<StructuredLogDocument>,
  ) {}

  async log(level: string, service: string, message: string, context?: LogContext) {
    try {
      await this.logModel.create({
        level,
        service,
        message,
        correlationId: context?.correlationId,
        sessionId: context?.sessionId,
        userId: context?.userId,
        requestId: context?.requestId,
        metadata: context ? Object.fromEntries(
          Object.entries(context).filter(([k]) => !['correlationId', 'sessionId', 'userId', 'requestId', 'stack'].includes(k))
        ) : undefined,
        stack: context?.stack,
      });
    } catch {
      // Don't let logging failures break the application
    }
  }

  async info(service: string, message: string, context?: LogContext) {
    return this.log('info', service, message, context);
  }

  async warn(service: string, message: string, context?: LogContext) {
    return this.log('warn', service, message, context);
  }

  async error(service: string, message: string, context?: LogContext) {
    return this.log('error', service, message, context);
  }

  async getLogs(options: {
    limit?: number;
    service?: string;
    level?: string;
    correlationId?: string;
    sessionId?: string;
    startTime?: Date;
    endTime?: Date;
  }) {
    const query: any = {};
    if (options.service) query.service = options.service;
    if (options.level) query.level = options.level;
    if (options.correlationId) query.correlationId = options.correlationId;
    if (options.sessionId) query.sessionId = options.sessionId;
    if (options.startTime || options.endTime) {
      query.createdAt = {};
      if (options.startTime) query.createdAt.$gte = options.startTime;
      if (options.endTime) query.createdAt.$lte = options.endTime;
    }

    return this.logModel
      .find(query)
      .sort({ createdAt: -1 })
      .limit(options.limit || 100)
      .select('-__v')
      .exec();
  }

  async getLogStats(options: { startTime?: Date; endTime?: Date }) {
    const now = new Date();
    const lastHour = new Date(now.getTime() - 60 * 60 * 1000);
    const lastDay = new Date(now.getTime() - 24 * 60 * 60 * 1000);

    const [hourlyByService, dailyByService, hourlyByLevel] = await Promise.all([
      this.logModel.aggregate([
        { $match: { createdAt: { $gte: lastHour } } },
        { $group: { _id: '$service', count: { $sum: 1 } } },
        { $sort: { count: -1 } },
      ]),
      this.logModel.aggregate([
        { $match: { createdAt: { $gte: lastDay } } },
        { $group: { _id: '$service', count: { $sum: 1 } } },
        { $sort: { count: -1 } },
      ]),
      this.logModel.aggregate([
        { $match: { createdAt: { $gte: lastHour } } },
        { $group: { _id: '$level', count: { $sum: 1 } } },
        { $sort: { count: -1 } },
      ]),
    ]);

    return {
      hourly_by_service: hourlyByService.map(s => ({ service: s._id, count: s.count })),
      daily_by_service: dailyByService.map(s => ({ service: s._id, count: s.count })),
      hourly_by_level: hourlyByLevel.map(l => ({ level: l._id, count: l.count })),
    };
  }
}
