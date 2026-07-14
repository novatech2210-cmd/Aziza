import { IsString, MinLength, IsOptional, IsEnum, IsArray } from 'class-validator';
import { ApiKeyTier } from './api-key.schema';

export class CreateApiKeyDto {
  @IsString()
  @MinLength(1)
  name: string;

  @IsOptional()
  @IsEnum(ApiKeyTier)
  tier?: ApiKeyTier;

  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  scopes?: string[];
}

export class RotateApiKeyDto {
  @IsString()
  keyId: string;
}
