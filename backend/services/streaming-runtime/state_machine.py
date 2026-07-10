from enum import Enum, auto
import logging

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

class SessionStateMachine:
    def __init__(self, session_id):
        self.session_id = session_id
        self.state = SessionState.IDLE
        self.logger = logging.getLogger(f"Session-{session_id}")

    def transition_to(self, new_state: SessionState):
        self.logger.info(f"Transition: {self.state.name} -> {new_state.name}")
        self.state = new_state
        return self.state

    def is_active(self):
        return self.state in [SessionState.GENERATING, SessionState.STREAMING, SessionState.THINKING]
