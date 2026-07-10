import { Controller, Post, Body, Get } from '@nestjs/common';
import { AuthService } from './auth.service';

@Controller('auth')
export class AuthController {
  constructor(private authService: AuthService) {}

  @Post('login')
  async login(@Body() body: any) {
    const payload = { username: body.username || 'testuser', sub: body.userId || '1' };
    return this.authService.generateToken(payload);
  }

  @Post('register')
  async register(@Body() body: any) {
    const payload = { username: body.username || 'testuser', sub: body.userId || '1' };
    return this.authService.generateToken(payload);
  }

  @Post('refresh')
  async refresh(@Body() body: any) {
    const payload = { username: 'testuser', sub: '1' };
    return this.authService.generateToken(payload);
  }

  @Get('me')
  async getMe() {
    return { role: 'admin', username: 'testuser', tier: 'enterprise' };
  }

  @Get('me/tier')
  async getTier() {
    return { tier: 'enterprise' };
  }

  @Get('chat-history')
  async getChatHistory() {
    return [];
  }

  @Post('chat-history')
  async saveChatHistory() {
    return { success: true };
  }
}
