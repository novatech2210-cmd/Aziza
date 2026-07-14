import { Controller, Post, Body, Get, UseGuards, Request } from '@nestjs/common';
import { Throttle } from '@nestjs/throttler';
import { AuthService } from './auth.service';
import { CreateUserDto } from './dto/create-user.dto';
import { LoginUserDto } from './dto/login-user.dto';
import { JwtAuthGuard } from './jwt-auth.guard';

@Controller('auth')
export class AuthController {
  constructor(private authService: AuthService) {}

  @Post('register')
  @Throttle({ auth: { limit: 3, ttl: 60000 } })
  async register(@Body() dto: CreateUserDto) {
    return this.authService.createUser(dto);
  }

  @Post('login')
  @Throttle({ auth: { limit: 5, ttl: 60000 } })
  async login(@Body() dto: LoginUserDto) {
    return this.authService.login(dto);
  }

  @Post('refresh')
  @UseGuards(JwtAuthGuard)
  async refresh(@Request() req) {
    return this.authService.refreshToken(req.user.userId);
  }

  @Get('me')
  @UseGuards(JwtAuthGuard)
  async getMe(@Request() req) {
    return this.authService.getUserById(req.user.userId);
  }

  @Get('me/tier')
  @UseGuards(JwtAuthGuard)
  async getTier(@Request() req) {
    const user = await this.authService.getUserById(req.user.userId);
    return { tier: user.role === 'admin' ? 'enterprise' : 'free' };
  }

  @Get('chat-history')
  @UseGuards(JwtAuthGuard)
  async getChatHistory(@Request() req) {
    return [];
  }

  @Post('chat-history')
  @UseGuards(JwtAuthGuard)
  async saveChatHistory(@Request() req, @Body() body: any) {
    return { success: true };
  }
}
