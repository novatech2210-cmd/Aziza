import { CanActivate, ExecutionContext, Injectable, UnauthorizedException } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { ApiKeyService } from './api-key.service';

export const REQUIRES_API_KEY = 'requires_api_key';

@Injectable()
export class ApiKeyGuard implements CanActivate {
  constructor(
    private reflector: Reflector,
    private apiKeyService: ApiKeyService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const requiresApiKey = this.reflector.getAllAndOverride<boolean>(REQUIRES_API_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);

    if (!requiresApiKey) {
      return true;
    }

    const request = context.switchToHttp().getRequest();
    const apiKey = request.headers['x-api-key'];

    if (!apiKey) {
      throw new UnauthorizedException('API key required. Provide X-Api-Key header.');
    }

    try {
      const keyData = await this.apiKeyService.validateKey(apiKey);
      request.apiKey = keyData;
      return true;
    } catch (error) {
      throw new UnauthorizedException(`Invalid API key: ${error.message}`);
    }
  }
}
