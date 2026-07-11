import { Injectable } from '@nestjs/common';
import { InjectConnection } from '@nestjs/mongoose';
import { Connection } from 'mongoose';

@Injectable()
export class AppService {
  constructor(@InjectConnection() private mongoConnection: Connection) {}

  async getHealth(): Promise<{ status: string; mongo: string }> {
    const mongoReady = this.mongoConnection.readyState === 1;
    return {
      status: mongoReady ? 'ok' : 'degraded',
      mongo: mongoReady ? 'connected' : 'disconnected',
    };
  }
}
