import { Injectable, UnauthorizedException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';

@Injectable()
export class AuthService {
  constructor(private jwtService: JwtService) {}

  async generateToken(payload: any) {
    return {
      access_token: this.jwtService.sign(payload),
    };
  }

  async validateUser(payload: any) {
    // In a real application, you would check if the user exists in a database here.
    if (!payload || !payload.sub) {
      throw new UnauthorizedException();
    }
    return payload;
  }
}
