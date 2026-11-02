import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from strands import Agent
from strands.models.ollama import OllamaModel

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "https://ollama.com")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:31b")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are a helpful assistant.")

if not OLLAMA_API_KEY:
    raise RuntimeError("OLLAMA_API_KEY environment variable is required")

model = OllamaModel(
    host=OLLAMA_HOST,
    model_id=OLLAMA_MODEL,
    ollama_client_args={"headers": {"Authorization": f"Bearer {OLLAMA_API_KEY}"}},
)

app = FastAPI(title="Strands Ollama Agent")


class ChatRequest(BaseModel):
    prompt: str


class ChatResponse(BaseModel):
    response: str
    model: str


@app.get("/health")
def health():
    return {"status": "ok", "model": OLLAMA_MODEL}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must not be empty")
    # New agent per request so conversation history isn't shared between callers.
    agent = Agent(model=model, system_prompt=SYSTEM_PROMPT, callback_handler=None)
    try:
        result = await agent.invoke_async(req.prompt)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model call failed: {e}")
    return ChatResponse(response=str(result).strip(), model=OLLAMA_MODEL)
