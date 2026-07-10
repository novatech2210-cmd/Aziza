from pydantic import BaseModel

class Persona(BaseModel):
    persona_id: str
    language: str
    base_prompt: str
