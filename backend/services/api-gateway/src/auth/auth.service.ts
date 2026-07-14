import { Injectable, UnauthorizedException, ConflictException, NotFoundException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import * as bcrypt from 'bcryptjs';
import { User, UserDocument, UserRole } from './schemas/user.schema';
import { CreateUserDto } from './dto/create-user.dto';
import { LoginUserDto } from './dto/login-user.dto';

@Injectable()
export class AuthService {
  constructor(
    private jwtService: JwtService,
    @InjectModel(User.name) private userModel: Model<UserDocument>,
  ) {}

  async createUser(dto: CreateUserDto): Promise<{ access_token: string; user: any }> {
    const existing = await this.userModel.findOne({ email: dto.email.toLowerCase() });
    if (existing) {
      throw new ConflictException('Email already registered');
    }

    const passwordHash = await bcrypt.hash(dto.password, 10);
    const user = await this.userModel.create({
      email: dto.email.toLowerCase(),
      passwordHash,
      role: dto.role || UserRole.USER,
    });

    const tokenPayload = { sub: user._id.toString(), email: user.email, role: user.role };
    const access_token = this.jwtService.sign(tokenPayload);

    return {
      access_token,
      user: {
        id: user._id,
        email: user.email,
        role: user.role,
      },
    };
  }

  async login(dto: LoginUserDto): Promise<{ access_token: string; user: any }> {
    const user = await this.userModel.findOne({ email: dto.email.toLowerCase() });
    if (!user) {
      throw new UnauthorizedException('Invalid credentials');
    }

    if (!user.isActive) {
      throw new UnauthorizedException('Account is disabled');
    }

    const passwordValid = await bcrypt.compare(dto.password, user.passwordHash);
    if (!passwordValid) {
      throw new UnauthorizedException('Invalid credentials');
    }

    await this.userModel.findByIdAndUpdate(user._id, { lastLoginAt: new Date() });

    const tokenPayload = { sub: user._id.toString(), email: user.email, role: user.role };
    const access_token = this.jwtService.sign(tokenPayload);

    return {
      access_token,
      user: {
        id: user._id,
        email: user.email,
        role: user.role,
      },
    };
  }

  async refreshToken(userId: string): Promise<{ access_token: string }> {
    const user = await this.userModel.findById(userId);
    if (!user || !user.isActive) {
      throw new UnauthorizedException('User not found or inactive');
    }

    const tokenPayload = { sub: user._id.toString(), email: user.email, role: user.role };
    const access_token = this.jwtService.sign(tokenPayload);

    return { access_token };
  }

  async getUserById(userId: string): Promise<any> {
    const user = await this.userModel.findById(userId).select('-passwordHash');
    if (!user) {
      throw new NotFoundException('User not found');
    }
    return user;
  }

  async getUserByEmail(email: string): Promise<UserDocument | null> {
    return this.userModel.findOne({ email: email.toLowerCase() });
  }

  async validateUser(payload: any) {
    if (!payload || !payload.sub) {
      throw new UnauthorizedException();
    }

    const user = await this.userModel.findById(payload.sub);
    if (!user || !user.isActive) {
      throw new UnauthorizedException();
    }

    return { userId: user._id.toString(), email: user.email, role: user.role };
  }

  async generateToken(payload: any) {
    return {
      access_token: this.jwtService.sign(payload),
    };
  }
}
