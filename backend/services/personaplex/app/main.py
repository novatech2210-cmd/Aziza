from fastapi import FastAPI
from app.api import prompt, persona, memory, lang

app = FastAPI()

app.include_router(prompt.router, prefix="/prompt")
app.include_router(persona.router, prefix="/persona")
app.include_router(memory.router, prefix="/memory")
app.include_router(lang.router, prefix="/lang")
@app.get("/health")
async def health():
    return {"status": "ok"}
