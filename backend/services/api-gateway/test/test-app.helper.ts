import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { AuthModule } from '../src/auth/auth.module';
import { MonitoringModule } from '../src/monitoring/monitoring.module';
import { AppController } from '../src/app.controller';
import { AppService } from '../src/app.service';
import { AdminController } from '../src/admin/admin.controller';

export async function createTestApp(): Promise<INestApplication> {
  const moduleFixture: TestingModule = await Test.createTestingModule({
    imports: [
      MongooseModule.forRoot(process.env.MONGODB_URI || 'mongodb://localhost:27017/aziza_test'),
      AuthModule,
      MonitoringModule,
    ],
    controllers: [AppController, AdminController],
    providers: [AppService],
  }).compile();

  const app = moduleFixture.createNestApplication();
  app.useGlobalPipes(new ValidationPipe({ transform: true, whitelist: true }));
  await app.init();
  return app;
}
