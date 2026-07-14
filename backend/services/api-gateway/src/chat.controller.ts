import {
  Controller,
  Post,
  UploadedFile,
  UseInterceptors,
  Body,
  HttpException,
  HttpStatus,
  Logger,
  Res,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { Response } from 'express';
import FormData from 'form-data';
import * as http from 'http';

const ASR_HOST = process.env.ASR_HOST || '127.0.0.1';
const ASR_PORT = parseInt(process.env.ASR_PORT || '8020');

// vLLM endpoints by language (same as chat.gateway.ts)
const VLLM_ENDPOINTS: Record<string, { host: string; port: number; model: string }> = {
  ru: {
    host: '127.0.0.1',
    port: 8002,
    model: 'Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24',
  },
  uz: {
    host: '127.0.0.1',
    port: 8003,
    model: 'alloma',
  },
  en: {
    host: '127.0.0.1',
    port: 8002,
    model: 'Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24',
  },
};

const SYSTEM_PROMPT =
  'You are Aziza, an advanced AI Assistant. Be helpful, concise, and friendly.';

// System prompts by language (same as chat.gateway.ts)
const SYSTEM_PROMPTS: Record<string, string> = {
  en: 'You are Aziza — a warm, intelligent, and attentive AI assistant. Speak naturally and conversationally. Keep responses concise. RESPOND ONLY IN ENGLISH.',
  ru: 'Ты Азиза — тёплый, умный и внимательный AI-ассистент. Говори естественно по-русски, как живой человек. Избегай формальных оборотов. Отвечай кратко и по делу. ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.',
  uz: "Siz Aziza — mehribon, aqlli va diqqatli AI yordamchisiz. O'zbek tilida tabiiy va jonli gapiring. Qisqa va aniq javob bering. FAQAT O'ZBEK TILIDA JAVOB BERING.",
};

/** Fire a JSON POST to a local HTTP service and return the parsed body. */
function postJson(
  host: string,
  port: number,
  path: string,
  body: object,
): Promise<any> {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const req = http.request(
      { host, port, path, method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) } },
      (res) => {
        let raw = '';
        res.on('data', (c) => (raw += c));
        res.on('end', () => {
          try { resolve(JSON.parse(raw)); }
          catch { reject(new Error(`Non-JSON response (${res.statusCode}): ${raw.slice(0, 200)}`)); }
        });
      },
    );
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

/** POST multipart/form-data to the ASR transcribe endpoint. */
function postAudioToASR(
  audioBuffer: Buffer,
  filename: string,
  mimetype: string,
  languageHint: string,
): Promise<any> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append('audio', audioBuffer, { filename, contentType: mimetype });
    form.append('language', languageHint);

    const headers = form.getHeaders();
    const formBuffer = form.getBuffer();

    const req = http.request(
      {
        host: ASR_HOST,
        port: ASR_PORT,
        path: '/transcribe',
        method: 'POST',
        headers: { ...headers, 'Content-Length': formBuffer.length },
      },
      (res) => {
        let raw = '';
        res.on('data', (c) => (raw += c));
        res.on('end', () => {
          if (res.statusCode === 200) {
            try { resolve(JSON.parse(raw)); }
            catch { reject(new Error(`ASR non-JSON: ${raw.slice(0, 200)}`)); }
          } else {
            reject(new Error(`ASR returned HTTP ${res.statusCode}: ${raw.slice(0, 200)}`));
          }
        });
      },
    );
    req.on('error', reject);
    req.write(formBuffer);
    req.end();
  });
}

@Controller('chat')
export class ChatController {
  private readonly logger = new Logger(ChatController.name);

  /**
   * POST /chat/voice
   * Accepts: multipart/form-data with fields:
   *   audio      — audio file (webm/ogg/wav)
   *   session_id — optional session identifier
   *   language   — optional hint: 'ru' | 'uz' | 'en'
   *
   * Returns:
   *   { transcription, response, detected_language, transcription_ms, inference_ms }
   */
  @Post('voice')
  @UseInterceptors(FileInterceptor('audio'))
  async voiceChat(
    @UploadedFile() file: Express.Multer.File,
    @Body('session_id') sessionId: string,
    @Body('language') languageHint: string,
  ): Promise<{
    transcription: string;
    response: string;
    detected_language: string;
    transcription_ms: number;
    inference_ms: number;
  }> {
    if (!file) {
      throw new HttpException('No audio file provided', HttpStatus.BAD_REQUEST);
    }

    this.logger.log(
      `Voice request: session=${sessionId || 'anon'} size=${file.size}B lang_hint=${languageHint || 'auto'}`,
    );

    // ── Step 1: Transcribe ────────────────────────────────────────────────
    const t0 = Date.now();
    let asrResult: any;
    try {
      asrResult = await postAudioToASR(
        file.buffer,
        file.originalname || 'recording.webm',
        file.mimetype || 'audio/webm',
        languageHint || '',
      );
    } catch (err) {
      this.logger.error(`ASR transcription failed: ${err.message}`);
      throw new HttpException(
        `Transcription failed: ${err.message}`,
        HttpStatus.BAD_GATEWAY,
      );
    }
    const transcriptionMs = Date.now() - t0;

    const transcription: string = asrResult.transcription || '(inaudible)';
    const detectedLang: string = asrResult.detected_language || languageHint || 'en';

    this.logger.log(
      `Transcribed in ${transcriptionMs}ms: "${transcription.slice(0, 80)}" [${detectedLang}]`,
    );

    // ── Step 2: LLM inference ─────────────────────────────────────────────
    const endpoint = VLLM_ENDPOINTS[detectedLang] ?? VLLM_ENDPOINTS['en'];
    const t1 = Date.now();
    let llmResult: any;
    try {
      llmResult = await postJson(
        endpoint.host,
        endpoint.port,
        '/v1/chat/completions',
        {
          model: endpoint.model,
          messages: [
            { role: 'system', content: SYSTEM_PROMPT },
            { role: 'user', content: transcription },
          ],
          max_tokens: 256,
          temperature: 0.7,
          stream: false,
        },
      );
    } catch (err) {
      this.logger.error(`LLM inference failed: ${err.message}`);
      throw new HttpException(
        `LLM inference failed: ${err.message}`,
        HttpStatus.BAD_GATEWAY,
      );
    }
    const inferenceMs = Date.now() - t1;

    const responseText: string =
      llmResult?.choices?.[0]?.message?.content?.trim() ?? '(no response)';

    this.logger.log(
      `Inference in ${inferenceMs}ms: "${responseText.slice(0, 80)}"`,
    );

    return {
      transcription,
      response: responseText,
      detected_language: detectedLang,
      transcription_ms: transcriptionMs,
      inference_ms: inferenceMs,
    };
  }

  /**
   * POST /chat/stream
   * Accepts: JSON body with fields:
   *   message   — user message text (required)
   *   language  — optional: 'ru' | 'uz' | 'en' (default: 'en')
   *   session_id — optional session identifier
   *
   * Returns: SSE stream with events:
   *   event: token
   *   data: {"content": "..."}
   *
   *   event: done
   *   data: {"total_ms": 1234}
   *
   *   event: error
   *   data: {"message": "..."}
   */
  @Post('stream')
  async streamChat(
    @Body('message') message: string,
    @Body('language') language: string,
    @Body('session_id') sessionId: string,
    @Res() res: Response,
  ) {
    if (!message?.trim()) {
      throw new HttpException('Message is required', HttpStatus.BAD_REQUEST);
    }

    const lang = language || 'en';
    const endpoint = VLLM_ENDPOINTS[lang] ?? VLLM_ENDPOINTS['en'];
    const systemPrompt = SYSTEM_PROMPTS[lang] || SYSTEM_PROMPTS.en;

    this.logger.log(
      `Stream request: session=${sessionId || 'anon'} lang=${lang} msg="${message.slice(0, 50)}"`,
    );

    // Set SSE headers
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');
    res.flushHeaders();

    const t0 = Date.now();
    let fullResponse = '';

    const body = JSON.stringify({
      model: endpoint.model,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: message },
      ],
      stream: true,
      max_tokens: 256,
      temperature: 0.6,
      top_p: 0.9,
      repetition_penalty: 1.1,
      presence_penalty: 0.3,
    });

    const req = http.request(
      {
        hostname: endpoint.host,
        port: endpoint.port,
        path: '/v1/chat/completions',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer EMPTY',
          'Content-Length': Buffer.byteLength(body),
        },
      },
      (vllmRes) => {
        if (vllmRes.statusCode !== 200) {
          let errBody = '';
          vllmRes.on('data', (c) => (errBody += c));
          vllmRes.on('end', () => {
            const errorMsg = `vLLM error (HTTP ${vllmRes.statusCode}): ${errBody.slice(0, 200)}`;
            this.logger.error(errorMsg);
            res.write(`event: error\ndata: ${JSON.stringify({ message: errorMsg })}\n\n`);
            res.end();
          });
          return;
        }

        let buffer = '';

        vllmRes.on('data', (chunk: Buffer) => {
          buffer += chunk.toString('utf-8');
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || !trimmed.startsWith('data: ')) continue;

            const dataStr = trimmed.slice(6).trim();
            if (dataStr === '[DONE]') {
              const totalMs = Date.now() - t0;
              res.write(
                `event: done\ndata: ${JSON.stringify({ total_ms: totalMs })}\n\n`,
              );
              res.end();
              this.logger.log(
                `Stream complete: ${totalMs}ms, ${fullResponse.length} chars`,
              );
              return;
            }

            try {
              const parsed = JSON.parse(dataStr);
              const token: string =
                parsed?.choices?.[0]?.delta?.content ?? '';
              if (token) {
                fullResponse += token;
                res.write(
                  `event: token\ndata: ${JSON.stringify({ content: token })}\n\n`,
                );
              }
            } catch {
              // Non-JSON line — skip
            }
          }
        });

        vllmRes.on('error', (err) => {
          this.logger.error(`vLLM stream error: ${err.message}`);
          res.write(
            `event: error\ndata: ${JSON.stringify({ message: 'Stream error from AI engine' })}\n\n`,
          );
          res.end();
        });
      },
    );

    req.on('error', (err) => {
      this.logger.error(`Could not reach vLLM: ${err.message}`);
      res.write(
        `event: error\ndata: ${JSON.stringify({ message: 'Could not reach the AI engine' })}\n\n`,
      );
      res.end();
    });

    // Handle client disconnect
    req.on('close', () => {
      if (!res.writableEnded) {
        res.end();
      }
    });

    req.write(body);
    req.end();
  }
}
