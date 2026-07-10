"""Voice Activity Detection (VAD) — energy-based with proper turn detection.

Uses short-time energy analysis with hysteresis and timing constraints
to detect speech segments and end-of-turn (silence after speech).

This approach is lightweight, has no ML dependencies, and provides
reliable turn detection for real-time voice pipelines.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

logger = logging.getLogger("VAD")


class VADState(Enum):
    """VAD FSM states."""
    IDLE = "idle"
    SPEAKING = "speaking"
    TRAILING_SILENCE = "trailing_silence"


@dataclass
class VADSession:
    """Per-session VAD state."""
    state: VADState = VADState.IDLE
    speech_start_time: float = 0.0
    last_speech_time: float = 0.0
    silence_start_time: float = 0.0
    speech_buffer: list = field(default_factory=list)
    energy_history: list = field(default_factory=list)
    total_speech_ms: float = 0.0
    total_silence_ms: float = 0.0
    utterance_count: int = 0
    noise_floor: float = 0.01  # Adaptive noise floor


class EnergyVAD:
    """Energy-based Voice Activity Detection.
    
    Detects speech using short-time energy analysis with:
    - Adaptive noise floor estimation
    - Hysteresis (separate thresholds for speech start/stop)
    - Minimum speech duration filter
    - Minimum silence duration for end-of-turn detection
    
    Parameters
    ----------
    speech_threshold_db : float
        Energy threshold (dB above noise floor) to detect speech start. Default -20.
    silence_threshold_db : float
        Energy threshold (dB above noise floor) to detect speech stop. Default -25.
        Must be lower than speech_threshold_db for hysteresis.
    min_speech_ms : int
        Minimum speech duration to trigger speaking state (ms). Default 250.
    min_silence_ms : int
        Minimum silence duration after speech to trigger end-of-turn (ms). Default 500.
    sample_rate : int
        Input audio sample rate. Default 24000.
    frame_ms : int
        Analysis frame size (ms). Default 30.
    noise_adapt_rate : float
        Noise floor adaptation rate (0-1). Lower = slower adaptation. Default 0.02.
    max_buffer_ms : int
        Maximum audio buffer size (ms). Prevents memory issues. Default 30000.
    """
    
    def __init__(
        self,
        speech_threshold_db: float = -20.0,
        silence_threshold_db: float = -25.0,
        min_speech_ms: int = 250,
        min_silence_ms: int = 500,
        sample_rate: int = 24000,
        frame_ms: int = 30,
        noise_adapt_rate: float = 0.02,
        max_buffer_ms: int = 30000,
    ):
        self.speech_threshold_db = speech_threshold_db
        self.silence_threshold_db = silence_threshold_db
        self.min_speech_ms = min_speech_ms
        self.min_silence_ms = min_silence_ms
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * frame_ms / 1000)
        self.noise_adapt_rate = noise_adapt_rate
        self.max_buffer_samples = int(sample_rate * max_buffer_ms / 1000)
        
        # Convert dB thresholds to linear energy
        # These are relative to noise floor
        self.speech_energy_threshold = 10 ** (speech_threshold_db / 10)
        self.silence_energy_threshold = 10 ** (silence_threshold_db / 10)
        
        logger.info(
            f"Energy VAD initialized: speech_th={speech_threshold_db}dB, "
            f"silence_th={silence_threshold_db}dB, min_speech={min_speech_ms}ms, "
            f"min_silence={min_silence_ms}ms"
        )
    
    def _compute_frame_energy(self, frame: np.ndarray) -> float:
        """Compute normalized RMS energy of a frame."""
        if len(frame) == 0:
            return 0.0
        return float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)) / 32768.0)
    
    def _energy_to_db(self, energy: float) -> float:
        """Convert linear energy to dB (relative to full scale)."""
        if energy <= 0:
            return -100.0
        return 20 * np.log10(energy + 1e-10)
    
    def _is_speech_frame(self, energy: float, noise_floor: float) -> bool:
        """Check if frame energy exceeds speech threshold relative to noise floor."""
        if noise_floor <= 0:
            return energy > 0.01
        relative_energy = energy / noise_floor
        return relative_energy >= self.speech_energy_threshold
    
    def _is_silence_frame(self, energy: float, noise_floor: float) -> bool:
        """Check if frame energy is below silence threshold relative to noise floor."""
        if noise_floor <= 0:
            return energy < 0.005
        relative_energy = energy / noise_floor
        return relative_energy < self.silence_energy_threshold
    
    def process_chunk(self, session: VADSession, audio_chunk: np.ndarray) -> dict:
        """Process an audio chunk and return VAD decision.
        
        Parameters
        ----------
        session : VADSession
            Per-session VAD state (mutated in place).
        audio_chunk : np.ndarray
            Int16 PCM audio chunk.
            
        Returns
        -------
        dict with keys:
            - is_speech: bool - whether speech is detected in this chunk
            - is_end_of_turn: bool - whether user finished speaking
            - speech_duration_ms: float - total speech duration in current utterance
            - energy_db: float - current frame energy in dB
            - noise_floor_db: float - estimated noise floor in dB
            - state: str - current VAD state
        """
        now = time.monotonic()
        
        # Process frame by frame for accurate detection
        is_speech_detected = False
        avg_energy = 0.0
        frame_count = 0
        
        for i in range(0, len(audio_chunk), self.frame_size):
            frame = audio_chunk[i:i + self.frame_size]
            if len(frame) < self.frame_size // 2:
                continue
                
            energy = self._compute_frame_energy(frame)
            avg_energy += energy
            frame_count += 1
            
            # Adaptive noise floor estimation (only during silence)
            if session.state == VADState.IDLE:
                session.noise_floor = (
                    (1 - self.noise_adapt_rate) * session.noise_floor
                    + self.noise_adapt_rate * energy
                )
            
            # Check speech detection
            if self._is_speech_frame(energy, max(session.noise_floor, 0.001)):
                is_speech_detected = True
        
        if frame_count > 0:
            avg_energy /= frame_count
        
        energy_db = self._energy_to_db(avg_energy)
        noise_floor_db = self._energy_to_db(max(session.noise_floor, 1e-6))
        
        result = {
            "is_speech": is_speech_detected,
            "is_end_of_turn": False,
            "speech_duration_ms": session.total_speech_ms,
            "energy_db": energy_db,
            "noise_floor_db": noise_floor_db,
            "state": session.state.value,
        }
        
        # State machine transitions
        if session.state == VADState.IDLE:
            if is_speech_detected:
                session.state = VADState.SPEAKING
                session.speech_start_time = now
                session.last_speech_time = now
                session.total_speech_ms = 0.0
                session.total_silence_ms = 0.0
                result["state"] = VADState.SPEAKING.value
                logger.debug(f"Speech started (energy: {energy_db:.1f}dB, noise: {noise_floor_db:.1f}dB)")
        
        elif session.state == VADState.SPEAKING:
            if is_speech_detected:
                session.last_speech_time = now
                session.total_speech_ms = (now - session.speech_start_time) * 1000
                session.total_silence_ms = 0.0
                result["state"] = VADState.SPEAKING.value
            else:
                # Speech stopped, enter trailing silence
                session.state = VADState.TRAILING_SILENCE
                session.silence_start_time = now
                session.total_silence_ms = 0.0
                result["state"] = VADState.TRAILING_SILENCE.value
                logger.debug(f"Speech stopped, monitoring silence")
        
        elif session.state == VADState.TRAILING_SILENCE:
            if is_speech_detected:
                # Resumed speaking
                session.state = VADState.SPEAKING
                session.last_speech_time = now
                session.total_speech_ms = (now - session.speech_start_time) * 1000
                session.total_silence_ms = 0.0
                result["state"] = VADState.SPEAKING.value
                logger.debug(f"Speech resumed")
            else:
                session.total_silence_ms = (now - session.silence_start_time) * 1000
                speech_duration = (now - session.speech_start_time) * 1000
                
                if (
                    session.total_silence_ms >= self.min_silence_ms
                    and speech_duration >= self.min_speech_ms
                ):
                    # End of turn detected
                    session.state = VADState.IDLE
                    session.utterance_count += 1
                    session.total_speech_ms = speech_duration
                    result["is_end_of_turn"] = True
                    result["is_speech"] = False
                    result["state"] = VADState.IDLE.value
                    result["speech_duration_ms"] = speech_duration
                    logger.info(
                        f"End of turn #{session.utterance_count}: "
                        f"speech={speech_duration:.0f}ms, "
                        f"silence={session.total_silence_ms:.0f}ms"
                    )
                else:
                    result["state"] = VADState.TRAILING_SILENCE.value
        
        return result
    
    def reset(self, session: VADSession):
        """Reset session VAD state."""
        session.state = VADState.IDLE
        session.speech_start_time = 0.0
        session.last_speech_time = 0.0
        session.silence_start_time = 0.0
        session.speech_buffer.clear()
        session.energy_history.clear()
        session.total_speech_ms = 0.0
        session.total_silence_ms = 0.0
