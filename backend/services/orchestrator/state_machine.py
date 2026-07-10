from enum import Enum

class SessionState(Enum):
    IDLE = 'IDLE'
    LISTENING = 'LISTENING'
    THINKING = 'THINKING'
    GENERATING = 'GENERATING'
    STREAMING = 'STREAMING'
    INTERRUPTING = 'INTERRUPTING'
    RECOVERING = 'RECOVERING'

class SessionContext:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = SessionState.IDLE
        self.last_activity = 0
        self.text_prompt = None
        self.voice_prompt = None
        self.active_inference_id = None
