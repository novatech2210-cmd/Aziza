import { Test, TestingModule } from '@nestjs/testing';
import { getModelToken } from '@nestjs/mongoose';
import { ApiKeyService } from './api-key.service';
import { ApiKey, ApiKeyTier } from './api-key.schema';
import { hashApiKey } from './api-key.schema';

describe('ApiKeyService', () => {
  let service: ApiKeyService;
  let mockApiKeyModel: any;

  const mockKey = {
    _id: 'key123',
    userId: 'user123',
    keyHash: 'abc123',
    keyPrefix: 'aziza_abc',
    name: 'Test Key',
    tier: ApiKeyTier.FREE,
    scopes: [],
    isActive: true,
    requestCount: 0,
    createdAt: new Date(),
  };

  beforeEach(async () => {
    mockApiKeyModel = {
      create: jest.fn().mockResolvedValue(mockKey),
      find: jest.fn().mockReturnValue({
        select: jest.fn().mockReturnValue({
          sort: jest.fn().mockResolvedValue([mockKey]),
        }),
      }),
      findOne: jest.fn().mockResolvedValue(mockKey),
      findByIdAndUpdate: jest.fn().mockResolvedValue(mockKey),
      findByIdAndDelete: jest.fn().mockResolvedValue(mockKey),
      countDocuments: jest.fn().mockResolvedValue(1),
      aggregate: jest.fn().mockResolvedValue([{ totalRequests: 10 }]),
    };

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ApiKeyService,
        { provide: getModelToken(ApiKey.name), useValue: mockApiKeyModel },
      ],
    }).compile();

    service = module.get<ApiKeyService>(ApiKeyService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('createKey', () => {
    it('should create a new API key', async () => {
      const result = await service.createKey('user123', { name: 'Test Key' });
      expect(result.key).toMatch(/^aziza_/);
      expect(result.apiKey).toBeDefined();
      expect(mockApiKeyModel.create).toHaveBeenCalled();
    });
  });

  describe('listKeys', () => {
    it('should list keys for a user', async () => {
      const result = await service.listKeys('user123');
      expect(result).toEqual([mockKey]);
    });
  });

  describe('revokeKey', () => {
    it('should revoke a key', async () => {
      await service.revokeKey('user123', 'key123');
      expect(mockApiKeyModel.findByIdAndUpdate).toHaveBeenCalledWith('key123', { isActive: false });
    });
  });

  describe('validateKey', () => {
    it('should validate a valid key', async () => {
      const rawKey = 'aziza_test123';
      const hash = hashApiKey(rawKey);
      mockApiKeyModel.findOne.mockResolvedValue({ ...mockKey, keyHash: hash });

      const result = await service.validateKey(rawKey);
      expect(result.userId).toBe('user123');
      expect(result.tier).toBe(ApiKeyTier.FREE);
    });

    it('should throw for invalid key', async () => {
      mockApiKeyModel.findOne.mockResolvedValue(null);
      await expect(service.validateKey('invalid')).rejects.toThrow('Invalid API key');
    });
  });

  describe('getKeyStats', () => {
    it('should return key statistics', async () => {
      const result = await service.getKeyStats('user123');
      expect(result.total).toBe(1);
      expect(result.active).toBe(1);
      expect(result.totalRequests).toBe(10);
    });
  });
});
