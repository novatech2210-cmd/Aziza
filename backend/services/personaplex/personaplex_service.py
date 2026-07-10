from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI()

class LangDetectRequest(BaseModel):
    text: str

@app.get("/health")
def health():
    return {"status": "ok", "service": "personaplex"}

@app.post("/lang/detect")
def lang_detect(request: LangDetectRequest):
    text = request.text.lower()
    if any(c in text for c in 'аеёийоуъыьэюя'):
        return {"lang": "ru", "confidence": 0.95}
    elif any(c in text for c in 'ўғҳқ'):
        return {"lang": "uz", "confidence": 0.95}
    else:
        return {"lang": "en", "confidence": 0.8}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
