import { Controller, Get, Query, HttpException } from '@nestjs/common';
import { AppService } from './app.service';
import * as http from 'http';

@Controller()
export class AppController {
  constructor(private readonly appService: AppService) {}

  @Get('health')
  async getHealth() {
    return this.appService.getHealth();
  }

  @Get('api/health-check')
  async healthCheck(@Query('port') port: string): Promise<{ status: string }> {
    const portNum = parseInt(port, 10);
    if (!portNum || portNum < 1 || portNum > 65535) {
      throw new HttpException('Invalid port', 400);
    }

    return new Promise((resolve, reject) => {
      const req = http.get(`http://127.0.0.1:${portNum}/`, { timeout: 3000 }, (res) => {
        resolve({ status: res.statusCode === 200 ? 'ok' : 'degraded' });
      });
      req.on('error', () => resolve({ status: 'down' }));
      req.on('timeout', () => { req.destroy(); resolve({ status: 'down' }); });
    });
  }
}
