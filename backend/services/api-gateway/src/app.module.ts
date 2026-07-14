import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ThrottlerModule } from '@nestjs/throttler';
import { MongooseModule } from '@nestjs/mongoose';
import { TerminusModule } from '@nestjs/terminus';
import { MulterModule } from '@nestjs/platform-express';
import { memoryStorage } from 'multer';
import { VoiceGateway } from './gateway/voice.gateway';
import { ChatGateway } from './gateway/chat.gateway';
import { AdminGateway } from './gateway/admin.gateway';
import { V2VGateway } from './gateway/v2v.gateway';
import { AdminController } from './admin/admin.controller';
import { ChatController } from './chat.controller';
import { LiveKitController } from './livekit.controller';
import { AuthModule } from './auth/auth.module';
import { MonitoringModule } from './monitoring/monitoring.module';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { ServeStaticModule } from '@nestjs/serve-static';
import { join } from 'path';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    ThrottlerModule.forRoot([{
      ttl: 60000,
      limit: 100,
    }]),
    MongooseModule.forRoot(process.env.MONGODB_URI || 'mongodb://localhost:27017/aziza'),
    TerminusModule,
    AuthModule,
    MonitoringModule,
    MulterModule.register({ storage: memoryStorage() }),
    ServeStaticModule.forRoot({
      rootPath: join(__dirname, '..', 'public'),
      exclude: ['/api/(.*)'],
    }),
  ],
  controllers: [AppController, AdminController, ChatController, LiveKitController],
  providers: [AppService, VoiceGateway, ChatGateway, AdminGateway, V2VGateway],
})
export class AppModule {}
