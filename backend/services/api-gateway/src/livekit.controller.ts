import {
  Controller,
  Post,
  Body,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { AccessToken } from 'livekit-server-sdk';

const LIVEKIT_API_KEY = process.env.LIVEKIT_API_KEY || 'devkey';
const LIVEKIT_API_SECRET = process.env.LIVEKIT_API_SECRET || 'devsecret';

@Controller('livekit')
export class LiveKitController {
  @Post('token')
  @HttpCode(HttpStatus.OK)
  async generateToken(@Body('roomName') roomName: string, @Body('participantName') participantName?: string) {
    if (!roomName) {
      return { error: 'roomName is required' };
    }

    const token = new AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET, {
      identity: participantName || `user-${Date.now()}`,
      name: participantName || 'User',
      ttl: '1h',
    });

    token.addGrant({
      roomJoin: true,
      room: roomName,
      canPublish: true,
      canSubscribe: true,
    });

    return {
      token: token.toJwt(),
      url: process.env.LIVEKIT_URL || 'ws://localhost:7880',
    };
  }
}
