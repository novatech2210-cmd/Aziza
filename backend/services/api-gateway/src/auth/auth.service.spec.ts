import { Test, TestingModule } from '@nestjs/testing';
import { JwtService } from '@nestjs/jwt';
import { getModelToken } from '@nestjs/mongoose';
import { AuthService } from './auth.service';
import { UnauthorizedException, ConflictException } from '@nestjs/common';
import { UserRole } from './schemas/user.schema';

describe('AuthService', () => {
  let service: AuthService;
  let jwtService: JwtService;
  let userModel: any;

  const mockUser = {
    _id: 'user123',
    email: 'test@example.com',
    passwordHash: '$2a$10$hashedpassword',
    role: UserRole.USER,
    isActive: true,
    lastLoginAt: null,
    preferences: {},
  };

  const mockUserModel = {
    findOne: jest.fn(),
    findById: jest.fn(),
    findByIdAndUpdate: jest.fn(),
    create: jest.fn(),
  };

  const mockJwtService = {
    sign: jest.fn().mockReturnValue('mock-token'),
  };

  beforeEach(async () => {
    jest.clearAllMocks();

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AuthService,
        { provide: JwtService, useValue: mockJwtService },
        { provide: getModelToken('User'), useValue: mockUserModel },
      ],
    }).compile();

    service = module.get<AuthService>(AuthService);
    jwtService = module.get<JwtService>(JwtService);
    userModel = module.get(getModelToken('User'));
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('createUser', () => {
    it('should create a new user and return token', async () => {
      mockUserModel.findOne.mockResolvedValue(null);
      mockUserModel.create.mockResolvedValue(mockUser);

      const result = await service.createUser({
        email: 'test@example.com',
        password: 'password123',
      });

      expect(result).toHaveProperty('access_token');
      expect(result).toHaveProperty('user');
      expect(result.user.email).toBe('test@example.com');
      expect(mockUserModel.create).toHaveBeenCalled();
    });

    it('should throw ConflictException if email exists', async () => {
      mockUserModel.findOne.mockResolvedValue(mockUser);

      await expect(
        service.createUser({ email: 'test@example.com', password: 'password123' }),
      ).rejects.toThrow(ConflictException);
    });
  });

  describe('login', () => {
    it('should return token for valid credentials', async () => {
      const bcrypt = require('bcryptjs');
      const hashedPassword = await bcrypt.hash('password123', 10);
      const userWithHash = { ...mockUser, passwordHash: hashedPassword };

      mockUserModel.findOne.mockResolvedValue(userWithHash);
      mockUserModel.findByIdAndUpdate.mockResolvedValue({});

      const result = await service.login({
        email: 'test@example.com',
        password: 'password123',
      });

      expect(result).toHaveProperty('access_token');
      expect(result.user.email).toBe('test@example.com');
    });

    it('should throw UnauthorizedException for invalid email', async () => {
      mockUserModel.findOne.mockResolvedValue(null);

      await expect(
        service.login({ email: 'wrong@example.com', password: 'password123' }),
      ).rejects.toThrow(UnauthorizedException);
    });

    it('should throw UnauthorizedException for invalid password', async () => {
      mockUserModel.findOne.mockResolvedValue(mockUser);

      await expect(
        service.login({ email: 'test@example.com', password: 'wrongpassword' }),
      ).rejects.toThrow(UnauthorizedException);
    });

    it('should throw UnauthorizedException for inactive user', async () => {
      mockUserModel.findOne.mockResolvedValue({ ...mockUser, isActive: false });

      await expect(
        service.login({ email: 'test@example.com', password: 'password123' }),
      ).rejects.toThrow(UnauthorizedException);
    });
  });

  describe('validateUser', () => {
    it('should return user for valid payload', async () => {
      mockUserModel.findById.mockResolvedValue(mockUser);

      const result = await service.validateUser({ sub: 'user123' });
      expect(result.userId).toBe('user123');
    });

    it('should throw UnauthorizedException for invalid payload', async () => {
      await expect(service.validateUser(null)).rejects.toThrow(UnauthorizedException);
      await expect(service.validateUser({})).rejects.toThrow(UnauthorizedException);
    });

    it('should throw UnauthorizedException for non-existent user', async () => {
      mockUserModel.findById.mockResolvedValue(null);
      await expect(service.validateUser({ sub: 'nonexistent' })).rejects.toThrow(UnauthorizedException);
    });
  });

  describe('generateToken', () => {
    it('should return an access_token', async () => {
      const result = await service.generateToken({ sub: 'user123', email: 'test@example.com' });
      expect(result).toHaveProperty('access_token');
      expect(result.access_token).toBe('mock-token');
    });
  });
});
