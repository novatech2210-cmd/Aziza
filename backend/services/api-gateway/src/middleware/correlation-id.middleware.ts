import { Injectable, NestMiddleware, Logger } from '@nestjs/common';
import { Request, Response, NextFunction } from 'express';
import { v4 as uuidv4 } from 'uuid';

export const CORRELATION_ID_HEADER = 'x-correlation-id';

@Injectable()
export class CorrelationIdMiddleware implements NestMiddleware {
  private readonly logger = new Logger(CorrelationIdMiddleware.name);

  use(req: Request, res: Response, next: NextFunction) {
    const existingId = req.headers[CORRELATION_ID_HEADER] as string | undefined;
    const correlationId = existingId || uuidv4();

    // Attach to request/response for downstream use
    (req as any).correlationId = correlationId;
    res.setHeader(CORRELATION_ID_HEADER, correlationId);

    // Log request with correlation ID
    const start = Date.now();
    const { method, originalUrl } = req;

    res.on('finish', () => {
      const duration = Date.now() - start;
      const status = res.statusCode;
      const entry = `${method} ${originalUrl} ${status} ${duration}ms [${correlationId}]`;
      if (status >= 500) console.error(entry);
      else if (status >= 400) console.warn(entry);
      else console.log(entry);
    });

    next();
  }
}
