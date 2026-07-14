from enum import Enum, auto
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("StateMachine")


class SessionState(Enum):
    IDLE = auto()
    LISTENING = auto()
    TRANSCRIBING = auto()
    THINKING = auto()
    GENERATING = auto()
    STREAMING = auto()
    INTERRUPTING = auto()
    CANCELLING = auto()
    RECOVERING = auto()

    @classmethod
    def active_states(cls):
        return {cls.GENERATING, cls.STREAMING, cls.THINKING}


# Valid state transitions: source -> set of allowed targets
VALID_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.IDLE: {SessionState.LISTENING, SessionState.INTERRUPTING},
    SessionState.LISTENING: {SessionState.TRANSCRIBING, SessionState.THINKING, SessionState.INTERRUPTING, SessionState.IDLE},
    SessionState.TRANSCRIBING: {SessionState.THINKING, SessionState.INTERRUPTING},
    SessionState.THINKING: {SessionState.GENERATING, SessionState.INTERRUPTING, SessionState.CANCELLING, SessionState.RECOVERING},
    SessionState.GENERATING: {SessionState.STREAMING, SessionState.INTERRUPTING, SessionState.CANCELLING},
    SessionState.STREAMING: {SessionState.LISTENING, SessionState.IDLE, SessionState.INTERRUPTING, SessionState.CANCELLING},
    SessionState.INTERRUPTING: {SessionState.RECOVERING, SessionState.LISTENING, SessionState.IDLE},
    SessionState.CANCELLING: {SessionState.IDLE, SessionState.RECOVERING},
    SessionState.RECOVERING: {SessionState.LISTENING, SessionState.IDLE},
}


@dataclass
class SessionContext:
    session_id: str
    state: SessionState = SessionState.IDLE
    last_activity: float = field(default_factory=time.time)
    state_entered_at: float = field(default_factory=time.time)
    transition_count: int = 0
    text_prompt: str = ""
    voice_prompt: str = ""
    active_inference_id: str = ""


class SessionStateMachine:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.context = SessionContext(session_id=session_id)
        self._transition_log: list[tuple[float, str, str]] = []

    @property
    def state(self) -> SessionState:
        return self.context.state

    def transition_to(self, new_state: SessionState) -> SessionState:
        old_state = self.context.state
        now = time.time()

        # Validate transition
        allowed = VALID_TRANSITIONS.get(old_state, set())
        if new_state not in allowed:
            logger.warning(
                f"[{self.session_id}] Invalid transition: {old_state.name} -> {new_state.name} "
                f"(allowed: {[s.name for s in allowed]})"
            )
            return old_state

        # Record transition
        duration_ms = (now - self.context.state_entered_at) * 1000
        self._transition_log.append((now, old_state.name, new_state.name))
        if len(self._transition_log) > 100:
            self._transition_log = self._transition_log[-50:]

        self.context.state = new_state
        self.context.state_entered_at = now
        self.context.last_activity = now
        self.context.transition_count += 1

        logger.info(
            f"[{self.session_id}] {old_state.name} -> {new_state.name} "
            f"(spent {duration_ms:.0f}ms in {old_state.name}, total transitions: {self.context.transition_count})"
        )
        return self.context.state

    def is_active(self) -> bool:
        return self.context.state in SessionState.active_states()

    def is_terminal(self) -> bool:
        return self.context.state in {SessionState.IDLE, SessionState.CANCELLING}

    def get_time_in_state(self) -> float:
        """Seconds since entering current state."""
        return time.time() - self.context.state_entered_at

    def get_transition_log(self) -> list[dict]:
        return [
            {"timestamp": ts, "from": old, "to": new}
            for ts, old, new in self._transition_log
        ]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "state": self.context.state.name,
            "transition_count": self.context.transition_count,
            "time_in_state_ms": self.get_time_in_state() * 1000,
            "is_active": self.is_active(),
            "recent_transitions": self.get_transition_log()[-10:],
        }
