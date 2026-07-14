import { Controller, Get, Post, Delete, Body, Param, UseGuards, Request } from '@nestjs/common';
import { Throttle } from '@nestjs/throttler';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { ApiKeyService } from './api-key.service';
import { CreateApiKeyDto } from './dto/create-api-key.dto';

@Controller('api-keys')
@UseGuards(JwtAuthGuard)
export class ApiKeyController {
  constructor(private apiKeyService: ApiKeyService) {}

  @Post()
  @Throttle({ default: { limit: 5, ttl: 60000 } })
  async createKey(@Request() req, @Body() dto: CreateApiKeyDto) {
    const { key, apiKey } = await this.apiKeyService.createKey(req.user.userId, dto);
    return {
      id: apiKey._id,
      name: apiKey.name,
      key,
      keyPrefix: apiKey.keyPrefix,
      tier: apiKey.tier,
      scopes: apiKey.scopes,
      createdAt: apiKey.createdAt,
      message: 'Save this key securely. It will not be shown again.',
    };
  }

  @Get()
  async listKeys(@Request() req) {
    return this.apiKeyService.listKeys(req.user.userId);
  }

  @Get('stats')
  async getStats(@Request() req) {
    return this.apiKeyService.getKeyStats(req.user.userId);
  }

  @Delete(':id')
  async revokeKey(@Request() req, @Param('id') id: string) {
    await this.apiKeyService.revokeKey(req.user.userId, id);
    return { success: true, message: 'API key revoked' };
  }

  @Delete(':id/permanent')
  async deleteKey(@Request() req, @Param('id') id: string) {
    await this.apiKeyService.deleteKey(req.user.userId, id);
    return { success: true, message: 'API key permanently deleted' };
  }
}
