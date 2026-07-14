import { Injectable, Logger, OnModuleInit, OnModuleDestroy } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import * as fs from 'fs';
import * as path from 'path';
import { Cron, CronExpression } from '@nestjs/schedule';
import { StructuredLog, StructuredLogDocument } from './structured-logging.service';

export interface ParsedLogEntry {
  timestamp: string;
  level: string;
  service: string;
  message: string;
  module?: string;
  function?: string;
  line?: number;
  correlationId?: string;
  sessionId?: string;
  workerId?: string;
  userId?: string;
  metadata?: Record<string, any>;
  exception?: {
    type: string;
    message: string;
    traceback: string;
  };
}

interface FilePosition {
  inode: number;
  size: number;
}

const LOG_DIR = '/root/aziza-build/logs';

const PM2_LOG_FILES: Record<string, string> = {
  'api-gateway': 'api-gateway-out.log',
  'orchestrator': 'orchestrator-out.log',
  'moshi-worker': 'moshi-worker-out.log',
  'personaplex': 'personaplex-out.log',
  'vllm-english': 'vllm-english-out.log',
  'vllm-uzbek': 'vllm-uzbek-out.log',
  'livekit-bot': 'livekit-bot-out.log',
};

const PM2_ERROR_FILES: Record<string, string> = {
  'api-gateway': 'api-gateway-error.log',
  'orchestrator': 'orchestrator-error.log',
  'moshi-worker': 'moshi-worker-error.log',
  'personaplex': 'personaplex-error.log',
  'vllm-english': 'vllm-english-error.log',
  'vllm-uzbek': 'vllm-uzbek-error.log',
  'livekit-bot': 'livekit-bot-error.log',
};

@Injectable()
export class LogCollectorService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(LogCollectorService.name);
  private watchers: fs.FSWatcher[] = [];
  private filePositions: Map<string, FilePosition> = new Map();
  private readonly MAX_BATCH_SIZE = 100;
  private readonly MAX_LOG_AGE_DAYS = 7;

  constructor(
    @InjectModel(StructuredLog.name) private logModel: Model<StructuredLogDocument>,
  ) {}

  onModuleInit() {
    this.logger.log('Initializing log collector — watching PM2 log files');
    this.initializePositions();
    this.startWatching();
  }

  onModuleDestroy() {
    this.stopWatching();
  }

  private initializePositions() {
    const allFiles = { ...PM2_LOG_FILES, ...PM2_ERROR_FILES };
    for (const [service, filename] of Object.entries(allFiles)) {
      const filePath = path.join(LOG_DIR, filename);
      try {
        if (fs.existsSync(filePath)) {
          const stat = fs.statSync(filePath);
          this.filePositions.set(filePath, { inode: stat.ino, size: stat.size });
        }
      } catch {
        // File doesn't exist yet, will be watched when created
      }
    }
  }

  private startWatching() {
    const allFiles = { ...PM2_LOG_FILES, ...PM2_ERROR_FILES };

    for (const [service, filename] of Object.entries(allFiles)) {
      const filePath = path.join(LOG_DIR, filename);
      this.watchFile(service, filePath);
    }

    // Also watch the log directory for new files
    try {
      const watcher = fs.watch(LOG_DIR, (eventType, filename) => {
        if (eventType === 'rename' && filename) {
          const fullPath = path.join(LOG_DIR, filename);
          if (fs.existsSync(fullPath) && !this.filePositions.has(fullPath)) {
            const service = this.detectServiceFromFile(filename);
            if (service) {
              this.watchFile(service, fullPath);
            }
          }
        }
      });
      this.watchers.push(watcher);
    } catch (err) {
      this.logger.warn(`Failed to watch log directory: ${err}`);
    }
  }

  private watchFile(service: string, filePath: string) {
    try {
      const watcher = fs.watch(filePath, () => {
        this.readNewLines(service, filePath);
      });
      watcher.on('error', () => {
        // File may have been rotated, re-initialize position
        this.filePositions.delete(filePath);
      });
      this.watchers.push(watcher);
      this.logger.debug(`Watching ${filePath} for service ${service}`);
    } catch (err) {
      this.logger.warn(`Failed to watch ${filePath}: ${err}`);
    }
  }

  private async readNewLines(service: string, filePath: string) {
    try {
      if (!fs.existsSync(filePath)) return;

      const stat = fs.statSync(filePath);
      const pos = this.filePositions.get(filePath);

      if (!pos || stat.size < pos.size) {
        // File was rotated/truncated, reset position
        this.filePositions.set(filePath, { inode: stat.ino, size: 0 });
        return;
      }

      if (stat.size === pos.size) return;

      const fd = fs.openSync(filePath, 'r');
      const buffer = Buffer.alloc(stat.size - pos.size);
      fs.readSync(fd, buffer, 0, buffer.length, pos.size);
      fs.closeSync(fd);

      this.filePositions.set(filePath, { inode: stat.ino, size: stat.size });

      const newContent = buffer.toString('utf-8');
      const lines = newContent.split('\n').filter(line => line.trim());

      const entries: ParsedLogEntry[] = [];
      for (const line of lines) {
        const parsed = this.parseLogLine(service, line);
        if (parsed) entries.push(parsed);
      }

      if (entries.length > 0) {
        await this.storeLogs(entries);
      }
    } catch (err) {
      this.logger.warn(`Error reading ${filePath}: ${err}`);
    }
  }

  private parseLogLine(defaultService: string, line: string): ParsedLogEntry | null {
    try {
      const parsed = JSON.parse(line);
      // Already structured JSON log from our Python services
      if (parsed.timestamp && parsed.level && parsed.message) {
        return {
          timestamp: parsed.timestamp,
          level: parsed.level.toLowerCase(),
          service: parsed.service || defaultService,
          message: parsed.message,
          module: parsed.module,
          function: parsed.function,
          line: parsed.line,
          correlationId: parsed.correlationId,
          sessionId: parsed.sessionId,
          workerId: parsed.workerId,
          userId: parsed.userId,
          metadata: parsed.metadata,
          exception: parsed.exception,
        };
      }
    } catch {
      // Not JSON — plain text log line (e.g., from vLLM or PM2 itself)
    }

    // Parse plain text log lines (PM2 format or vLLM output)
    const tsMatch = line.match(/^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})/);
    const levelMatch = line.match(/\b(ERROR|WARN|WARNING|INFO|DEBUG|CRITICAL)\b/i);

    return {
      timestamp: tsMatch ? tsMatch[1] : new Date().toISOString(),
      level: levelMatch ? levelMatch[1].toLowerCase() : 'info',
      service: defaultService,
      message: line.slice(0, 4096),
    };
  }

  private async storeLogs(entries: ParsedLogEntry[]) {
    try {
      const docs = entries.map(entry => ({
        level: entry.level,
        service: entry.service,
        message: entry.message,
        correlationId: entry.correlationId,
        sessionId: entry.sessionId,
        userId: entry.userId,
        metadata: entry.metadata,
        stack: entry.exception?.traceback,
        createdAt: new Date(entry.timestamp),
      }));

      await this.logModel.insertMany(docs, { ordered: false }).catch(() => {
        // Ignore duplicate key errors from capped collection
      });
    } catch (err) {
      this.logger.warn(`Failed to store ${entries.length} log entries: ${err}`);
    }
  }

  private detectServiceFromFile(filename: string): string | null {
    for (const [service, logFile] of Object.entries(PM2_LOG_FILES)) {
      if (filename === logFile || filename.startsWith(logFile.split('.')[0])) {
        return service;
      }
    }
    for (const [service, errFile] of Object.entries(PM2_ERROR_FILES)) {
      if (filename === errFile || filename.startsWith(errFile.split('.')[0])) {
        return service;
      }
    }
    return null;
  }

  private stopWatching() {
    for (const watcher of this.watchers) {
      try { watcher.close(); } catch {}
    }
    this.watchers = [];
  }

  @Cron(CronExpression.EVERY_HOUR)
  async cleanupOldLogs() {
    try {
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - this.MAX_LOG_AGE_DAYS);
      const result = await this.logModel.deleteMany({ createdAt: { $lt: cutoff } });
      if (result.deletedCount > 0) {
        this.logger.debug(`Cleaned up ${result.deletedCount} old log entries`);
      }
    } catch (err) {
      this.logger.warn(`Log cleanup failed: ${err}`);
    }
  }

  async getAggregatedLogs(options: {
    limit?: number;
    service?: string;
    level?: string;
    search?: string;
    startTime?: Date;
    endTime?: Date;
    correlationId?: string;
  }) {
    const query: any = {};
    if (options.service) query.service = options.service;
    if (options.level) query.level = options.level;
    if (options.correlationId) query.correlationId = options.correlationId;
    if (options.search) {
      query.$text = { $search: options.search };
    }
    if (options.startTime || options.endTime) {
      query.createdAt = {};
      if (options.startTime) query.createdAt.$gte = options.startTime;
      if (options.endTime) query.createdAt.$lte = options.endTime;
    }

    return this.logModel
      .find(query)
      .sort({ createdAt: -1 })
      .limit(options.limit || 200)
      .select('-__v')
      .exec();
  }

  async getLogStats() {
    const now = new Date();
    const lastHour = new Date(now.getTime() - 60 * 60 * 1000);
    const lastDay = new Date(now.getTime() - 24 * 60 * 60 * 1000);

    const [hourlyByService, hourlyByLevel, totalToday] = await Promise.all([
      this.logModel.aggregate([
        { $match: { createdAt: { $gte: lastHour } } },
        { $group: { _id: '$service', count: { $sum: 1 } } },
        { $sort: { count: -1 } },
      ]),
      this.logModel.aggregate([
        { $match: { createdAt: { $gte: lastHour } } },
        { $group: { _id: '$level', count: { $sum: 1 } } },
        { $sort: { count: -1 } },
      ]),
      this.logModel.countDocuments({ createdAt: { $gte: lastDay } }),
    ]);

    return {
      hourly_by_service: hourlyByService.map(s => ({ service: s._id, count: s.count })),
      hourly_by_level: hourlyByLevel.map(l => ({ level: l._id, count: l.count })),
      total_today: totalToday,
    };
  }
}
