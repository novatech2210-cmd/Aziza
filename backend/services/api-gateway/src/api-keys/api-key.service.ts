import { Injectable, NotFoundException, ForbiddenException, UnauthorizedException } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { ApiKey, ApiKeyDocument, ApiKeyTier, generateApiKey, hashApiKey } from './api-key.schema';
import { CreateApiKeyDto } from './dto/create-api-key.dto';

@Injectable()
export class ApiKeyService {
  constructor(
    @InjectModel(ApiKey.name) private apiKeyModel: Model<ApiKeyDocument>,
  ) {}

  async createKey(userId: string, dto: CreateApiKeyDto): Promise<{ key: string; apiKey: ApiKeyDocument }> {
    const { key, hash, prefix } = generateApiKey();

    const apiKey = await this.apiKeyModel.create({
      userId,
      keyHash: hash,
      keyPrefix: prefix,
      name: dto.name,
      tier: dto.tier || ApiKeyTier.FREE,
      scopes: dto.scopes || [],
    });

    return { key, apiKey };
  }

  async listKeys(userId: string): Promise<ApiKeyDocument[]> {
    return this.apiKeyModel.find({ userId }).select('-keyHash').sort({ createdAt: -1 });
  }

  async revokeKey(userId: string, keyId: string): Promise<void> {
    const key = await this.apiKeyModel.findOne({ _id: keyId, userId });
    if (!key) {
      throw new NotFoundException('API key not found');
    }
    await this.apiKeyModel.findByIdAndUpdate(keyId, { isActive: false });
  }

  async deleteKey(userId: string, keyId: string): Promise<void> {
    const key = await this.apiKeyModel.findOne({ _id: keyId, userId });
    if (!key) {
      throw new NotFoundException('API key not found');
    }
    await this.apiKeyModel.findByIdAndDelete(keyId);
  }

  async validateKey(rawKey: string): Promise<{ userId: string; tier: ApiKeyTier; scopes: string[] }> {
    const hash = hashApiKey(rawKey);
    const apiKey = await this.apiKeyModel.findOne({ keyHash: hash, isActive: true });

    if (!apiKey) {
      throw new UnauthorizedException('Invalid API key');
    }

    if (apiKey.expiresAt && apiKey.expiresAt < new Date()) {
      throw new UnauthorizedException('API key has expired');
    }

    await this.apiKeyModel.findByIdAndUpdate(apiKey._id, {
      lastUsedAt: new Date(),
      $inc: { requestCount: 1 },
    });

    return {
      userId: apiKey.userId,
      tier: apiKey.tier,
      scopes: apiKey.scopes,
    };
  }

  async getKeyStats(userId: string): Promise<{ total: number; active: number; totalRequests: number }> {
    const total = await this.apiKeyModel.countDocuments({ userId });
    const active = await this.apiKeyModel.countDocuments({ userId, isActive: true });
    const result = await this.apiKeyModel.aggregate([
      { $match: { userId } },
      { $group: { _id: null, totalRequests: { $sum: '$requestCount' } } },
    ]);
    return {
      total,
      active,
      totalRequests: result[0]?.totalRequests || 0,
    };
  }
}
