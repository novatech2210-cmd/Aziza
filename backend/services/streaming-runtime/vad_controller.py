"""VAD Controller using webrtcvad for speech detection."""

import webrtcvad
import collections
import logging

logger = logging.getLogger("VADController")


class VADController:
    """Voice Activity Detection controller with hysteresis."""

    def __init__(self, aggressiveness=3, sample_rate=16000, frame_duration_ms=30):
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        # Expected frame size in bytes (16-bit PCM = 2 bytes per sample)
        self.frame_size = int(sample_rate * frame_duration_ms / 1000) * 2
        self.num_padding_frames = 10
        self.ring_buffer = collections.deque(maxlen=self.num_padding_frames)
        self.triggered = False

    def is_speech(self, frame_bytes: bytes) -> bool:
        """Determine if a frame contains speech.

        Args:
            frame_bytes: Raw PCM audio bytes. Must be exactly
                         self.frame_size bytes (30ms of 16kHz 16-bit PCM = 960 bytes).

        Returns:
            True if speech is detected, False otherwise.
        """
        # Guard: webrtcvad requires exact frame sizes
        if len(frame_bytes) != self.frame_size:
            logger.debug(
                f"Skipping VAD: frame size {len(frame_bytes)} != expected {self.frame_size}"
            )
            return self.triggered  # Return current state for invalid frames

        try:
            is_speech = self.vad.is_speech(frame_bytes, self.sample_rate)
        except Exception as e:
            logger.warning(f"VAD processing error: {e}")
            return self.triggered

        if not self.triggered:
            self.ring_buffer.append((frame_bytes, is_speech))
            num_voiced = len([f for f, speech in self.ring_buffer if speech])
            if num_voiced > 0.9 * self.ring_buffer.maxlen:
                self.triggered = True
                self.ring_buffer.clear()
                return True
        else:
            self.ring_buffer.append((frame_bytes, is_speech))
            num_unvoiced = len([f for f, speech in self.ring_buffer if not speech])
            if num_unvoiced > 0.9 * self.ring_buffer.maxlen:
                self.triggered = False
                self.ring_buffer.clear()
                return False

        return self.triggered

    def reset(self):
        """Reset VAD state."""
        self.ring_buffer.clear()
        self.triggered = False
