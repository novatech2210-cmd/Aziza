"""Tests for the orchestrator state machine."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from state_machine import SessionState, SessionContext


class TestSessionState:
    def test_all_states_exist(self):
        assert SessionState.IDLE.value == 'IDLE'
        assert SessionState.LISTENING.value == 'LISTENING'
        assert SessionState.THINKING.value == 'THINKING'
        assert SessionState.GENERATING.value == 'GENERATING'
        assert SessionState.STREAMING.value == 'STREAMING'
        assert SessionState.INTERRUPTING.value == 'INTERRUPTING'
        assert SessionState.RECOVERING.value == 'RECOVERING'

    def test_state_count(self):
        assert len(SessionState) == 7


class TestSessionContext:
    def test_init(self):
        ctx = SessionContext("test-session-1")
        assert ctx.session_id == "test-session-1"
        assert ctx.state == SessionState.IDLE
        assert ctx.last_activity == 0
        assert ctx.text_prompt is None
        assert ctx.voice_prompt is None
        assert ctx.active_inference_id is None

    def test_state_transitions(self):
        ctx = SessionContext("test-session-2")
        assert ctx.state == SessionState.IDLE

        ctx.state = SessionState.LISTENING
        assert ctx.state == SessionState.LISTENING

        ctx.state = SessionState.THINKING
        assert ctx.state == SessionState.THINKING

        ctx.state = SessionState.GENERATING
        assert ctx.state == SessionState.GENERATING

        ctx.state = SessionState.STREAMING
        assert ctx.state == SessionState.STREAMING

        ctx.state = SessionState.INTERRUPTING
        assert ctx.state == SessionState.INTERRUPTING

        ctx.state = SessionState.RECOVERING
        assert ctx.state == SessionState.RECOVERING

    def test_multiple_contexts_isolated(self):
        ctx1 = SessionContext("session-1")
        ctx2 = SessionContext("session-2")

        ctx1.state = SessionState.THINKING
        ctx2.state = SessionState.LISTENING

        assert ctx1.state == SessionState.THINKING
        assert ctx2.state == SessionState.LISTENING
        assert ctx1.session_id != ctx2.session_id

    def test_prompt_assignment(self):
        ctx = SessionContext("test-session-3")
        ctx.text_prompt = "Hello, how are you?"
        ctx.voice_prompt = b"audio_data"

        assert ctx.text_prompt == "Hello, how are you?"
        assert ctx.voice_prompt == b"audio_data"

    def test_inference_id_tracking(self):
        ctx = SessionContext("test-session-4")
        assert ctx.active_inference_id is None

        ctx.active_inference_id = "inference-123"
        assert ctx.active_inference_id == "inference-123"

        ctx.active_inference_id = None
        assert ctx.active_inference_id is None

    def test_last_activity_tracking(self):
        import time
        ctx = SessionContext("test-session-5")
        assert ctx.last_activity == 0

        ctx.last_activity = time.time()
        assert ctx.last_activity > 0
