import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';
import * as crypto from 'crypto';

export type ApiKeyDocument = ApiKey & Document;

export enum ApiKeyTier {
  FREE = 'free',
  PRO = 'pro',
  ENTERPRISE = 'enterprise',
}

@Schema({ timestamps: true })
export class ApiKey {
  @Prop({ required: true })
  userId: string;

  @Prop({ required: true, unique: true })
  keyHash: string;

  @Prop({ required: true })
  keyPrefix: string;

  @Prop({ required: true })
  name: string;

  @Prop({ enum: ApiKeyTier, default: ApiKeyTier.FREE })
  tier: ApiKeyTier;

  @Prop({ type: [String], default: [] })
  scopes: string[];

  @Prop({ default: true })
  isActive: boolean;

  @Prop()
  lastUsedAt: Date;

  @Prop()
  expiresAt: Date;

  @Prop({ default: 0 })
  requestCount: number;
}

export const ApiKeySchema = SchemaFactory.createForClass(ApiKey);

ApiKeySchema.index({ userId: 1 });
ApiKeySchema.index({ keyHash: 1 }, { unique: true });
ApiKeySchema.index({ keyPrefix: 1 });

export function generateApiKey(): { key: string; hash: string; prefix: string } {
  const raw = crypto.randomBytes(32).toString('hex');
  const key = `aziza_${raw}`;
  const hash = crypto.createHash('sha256').update(key).digest('hex');
  const prefix = key.substring(0, 12);
  return { key, hash, prefix };
}

export function hashApiKey(key: string): string {
  return crypto.createHash('sha256').update(key).digest('hex');
}
