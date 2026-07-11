import { NestFactory } from '@nestjs/core';
import { ValidationPipe, Logger } from '@nestjs/common';
import { AppModule } from './app.module';
import { WsAdapter } from '@nestjs/platform-ws';
import { CorrelationIdMiddleware } from './middleware/correlation-id.middleware';
import { AllExceptionsFilter } from './filters/all-exceptions.filter';
import helmet from 'helmet';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  const logger = new Logger('Bootstrap');

  // Security headers
  app.use(helmet({
    contentSecurityPolicy: false,
    crossOriginEmbedderPolicy: false,
  }));

  // Global exception filter — structured error responses
  app.useGlobalFilters(new AllExceptionsFilter());

  // CORS — restrict to allowed origins
  const allowedOrigins = process.env.CORS_ORIGINS
    ? process.env.CORS_ORIGINS.split(',').map(s => s.trim())
    : ['http://localhost:5173', 'http://localhost:3000'];
  app.enableCors({
    origin: allowedOrigins,
    credentials: true,
  });

  app.useWebSocketAdapter(new WsAdapter(app));
  app.setGlobalPrefix('api');

  // Input validation — enforces DTO decorators (class-validator)
  app.useGlobalPipes(new ValidationPipe({
    whitelist: true,
    forbidNonWhitelisted: true,
    transform: true,
  }));

  // Apply correlation ID middleware globally
  app.use(new CorrelationIdMiddleware().use);

  const port = process.env.PORT || 3000;
  await app.listen(port);
  logger.log(`API Gateway is running on: http://localhost:${port}/api`);
}
bootstrap();
