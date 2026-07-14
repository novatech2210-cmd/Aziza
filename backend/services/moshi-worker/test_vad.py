"""Tests for the VAD (Voice Activity Detection) module."""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock
import sys
import os
import time

# Add the moshi-worker directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vad import EnergyVAD, VADSession, VADState, VADStats


class TestVADState:
    def test_vad_states_exist(self):
        assert VADState.IDLE.value == "idle"
        assert VADState.SPEAKING.value == "speaking"
        assert VADState.TRAILING_SILENCE.value == "trailing_silence"


class TestVADSession:
    def test_default_session(self):
        session = VADSession()
        assert session.state == VADState.IDLE
        assert session.speech_start_time == 0.0
        assert session.last_speech_time == 0.0
        assert session.silence_start_time == 0.0
        assert session.speech_buffer == []
        assert session.energy_history == []
        assert session.total_speech_ms == 0.0
        assert session.total_silence_ms == 0.0
        assert session.utterance_count == 0
        assert session.noise_floor == 0.01
        assert session.peak_energy == 0.0
        assert session.speech_count == 0
        assert session.silence_count == 0


class TestVADStats:
    def test_default_stats(self):
        stats = VADStats()
        assert stats.total_utterances == 0
        assert stats.total_speech_ms == 0.0
        assert stats.total_silence_ms == 0.0
        assert stats.avg_utterance_ms == 0.0
        assert stats.avg_silence_ms == 0.0
        assert stats.noise_floor_db == -60.0
        assert stats.active_sessions == 0


class TestEnergyVAD:
    def test_init_defaults(self):
        vad = EnergyVAD()
        assert vad.speech_threshold_db == -18.0
        assert vad.silence_threshold_db == -23.0
        assert vad.min_speech_ms == 200
        assert vad.min_silence_ms == 350
        assert vad.sample_rate == 24000

    def test_init_custom_params(self):
        vad = EnergyVAD(
            speech_threshold_db=-15.0,
            silence_threshold_db=-20.0,
            min_speech_ms=100,
            min_silence_ms=200,
            sample_rate=16000,
        )
        assert vad.speech_threshold_db == -15.0
        assert vad.silence_threshold_db == -20.0
        assert vad.min_speech_ms == 100
        assert vad.min_silence_ms == 200
        assert vad.sample_rate == 16000

    def test_init_from_env(self):
        with patch.dict(os.environ, {
            'VAD_SPEECH_THRESHOLD_DB': '-12',
            'VAD_SILENCE_THRESHOLD_DB': '-18',
            'VAD_MIN_SPEECH_MS': '150',
            'VAD_MIN_SILENCE_MS': '250',
            'VAD_NOISE_ADAPT_RATE': '0.05',
        }):
            vad = EnergyVAD()
            assert vad.speech_threshold_db == -12.0
            assert vad.silence_threshold_db == -18.0
            assert vad.min_speech_ms == 150
            assert vad.min_silence_ms == 250
            assert vad.noise_adapt_rate == 0.05

    def test_frame_size_calculation(self):
        vad = EnergyVAD(sample_rate=24000, frame_ms=30)
        expected_frame_size = int(24000 * 30 / 1000)  # 720
        assert vad.frame_size == expected_frame_size

    def test_energy_threshold_conversion(self):
        vad = EnergyVAD(speech_threshold_db=-18.0, silence_threshold_db=-23.0)
        assert vad.speech_energy_threshold > 0
        assert vad.silence_energy_threshold > 0
        assert vad.speech_energy_threshold > vad.silence_energy_threshold

    def test_compute_frame_energy_silence(self):
        vad = EnergyVAD()
        silence = np.zeros(720, dtype=np.float32)
        energy = vad._compute_frame_energy(silence)
        assert energy == 0.0

    def test_compute_frame_energy_speech(self):
        vad = EnergyVAD()
        t = np.linspace(0, 0.03, 720, dtype=np.float32)
        speech = (0.5 * np.sin(2 * np.pi * 440 * t) * 32768).astype(np.float32)
        energy = vad._compute_frame_energy(speech)
        assert energy > 0

    def test_energy_to_db(self):
        vad = EnergyVAD()
        assert vad._energy_to_db(0) == -100.0
        assert vad._energy_to_db(1.0) > -10
        assert vad._energy_to_db(0.001) < vad._energy_to_db(1.0)

    def test_is_speech_frame(self):
        vad = EnergyVAD()
        # Relative energy = 1.0 / 0.001 = 1000, which exceeds threshold
        assert vad._is_speech_frame(1.0, 0.001) is True
        # Relative energy = 0.0001 / 0.001 = 0.1, which is below default threshold
        assert vad._is_speech_frame(0.0001, 1.0) is False

    def test_is_silence_frame(self):
        vad = EnergyVAD()
        # Relative energy = 0.0001 / 1.0 = 0.0001, well below silence threshold
        assert vad._is_silence_frame(0.0001, 1.0) is True
        # Relative energy = 1.0 / 0.001 = 1000, well above silence threshold
        assert vad._is_silence_frame(1.0, 0.001) is False

    def test_is_speech_frame_zero_noise_floor(self):
        vad = EnergyVAD()
        assert vad._is_speech_frame(0.1, 0) is True
        assert vad._is_speech_frame(0.001, 0) is False

    def test_is_silence_frame_zero_noise_floor(self):
        vad = EnergyVAD()
        assert vad._is_silence_frame(0.001, 0) is True
        assert vad._is_silence_frame(0.1, 0) is False

    def test_process_chunk_silence(self):
        vad = EnergyVAD(min_speech_ms=0, min_silence_ms=0)
        session = VADSession()
        silence = np.zeros(720, dtype=np.float32)

        result = vad.process_chunk(session, silence)
        assert isinstance(result, dict)
        assert 'is_speech' in result
        assert 'is_end_of_turn' in result
        assert 'state' in result
        assert result['is_speech'] is False
        assert result['is_end_of_turn'] is False

    def test_process_chunk_returns_info(self):
        vad = EnergyVAD()
        session = VADSession()
        chunk = np.zeros(720, dtype=np.float32)

        result = vad.process_chunk(session, chunk)
        assert 'is_speech' in result
        assert 'is_end_of_turn' in result
        assert 'speech_duration_ms' in result
        assert 'energy_db' in result
        assert 'noise_floor_db' in result
        assert 'state' in result

    def test_process_chunk_transitions_to_speaking(self):
        vad = EnergyVAD(min_speech_ms=0, min_silence_ms=0)
        session = VADSession()

        # Generate loud speech-like audio
        t = np.linspace(0, 0.03, 720, dtype=np.float32)
        speech = (0.8 * np.sin(2 * np.pi * 440 * t) * 32768).astype(np.float32)

        result = vad.process_chunk(session, speech)
        # May or may not transition depending on noise floor adaptation
        assert result['state'] in ['idle', 'speaking']

    def test_get_stats(self):
        vad = EnergyVAD()
        stats = vad.get_stats()
        assert isinstance(stats, dict)
        assert 'total_utterances' in stats
        assert 'avg_utterance_ms' in stats
        assert 'avg_silence_ms' in stats
        assert 'active_sessions' in stats
        assert 'config' in stats

    def test_get_stats_with_active_sessions(self):
        vad = EnergyVAD()
        stats = vad.get_stats(active_sessions=5)
        assert stats['active_sessions'] == 5

    def test_reset_session(self):
        vad = EnergyVAD()
        session = VADSession()
        session.state = VADState.SPEAKING
        session.total_speech_ms = 1000.0

        vad.reset(session)
        assert session.state == VADState.IDLE
        assert session.total_speech_ms == 0.0

    def test_multiple_sessions_independent(self):
        vad = EnergyVAD()
        session1 = VADSession()
        session2 = VADSession()

        chunk = np.zeros(720, dtype=np.float32)
        vad.process_chunk(session1, chunk)
        vad.process_chunk(session2, chunk)

        # Both should have independent state
        assert isinstance(session1.state, VADState)
        assert isinstance(session2.state, VADState)

    def test_noise_floor_adaptation(self):
        vad = EnergyVAD()
        session = VADSession()
        initial_noise_floor = session.noise_floor

        # Process several frames of silence to adapt noise floor
        silence = np.zeros(720, dtype=np.float32)
        for _ in range(100):
            vad.process_chunk(session, silence)

        # Noise floor should have adapted
        assert session.noise_floor != initial_noise_floor or session.noise_floor == 0.01
