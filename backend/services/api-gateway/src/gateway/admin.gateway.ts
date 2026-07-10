import {
  WebSocketGateway,
  WebSocketServer,
  OnGatewayConnection,
  OnGatewayDisconnect,
} from '@nestjs/websockets';
import { Server } from 'ws';
import { Logger } from '@nestjs/common';

@WebSocketGateway({ 
  path: '/api/admin-stats',
  cors: { origin: '*' }
})
export class AdminGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;

  private readonly logger = new Logger(AdminGateway.name);
  private statsInterval: any;

  handleConnection(client: any, request: any) {
    this.logger.log(`Admin client connected: ${request.url}`);
    
    // Mock periodic stats for AdminView
    this.statsInterval = setInterval(() => {
      if (client.readyState === 1) {
        client.send(JSON.stringify({
          active_sessions: Math.floor(Math.random() * 10),
          gpu_0_util: Math.floor(Math.random() * 100),
          gpu_0_mem: 12000 + Math.floor(Math.random() * 1000),
          latency_p50: 10 + Math.floor(Math.random() * 20),
          latency_p95: 30 + Math.floor(Math.random() * 40)
        }));
      }
    }, 2000);
  }

  handleDisconnect(client: any) {
    if (this.statsInterval) {
      clearInterval(this.statsInterval);
    }
    this.logger.log('Admin client disconnected');
  }
}
