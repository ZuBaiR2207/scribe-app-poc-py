from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.transcribe_ws import router as transcribe_router
from app.config import get_settings
from app.speech.faster_whisper_engine import FasterWhisperEngine

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.engine = FasterWhisperEngine(settings.whisper_model, settings.whisper_compute_type)
    yield


app = FastAPI(title="Wellness Scribe POC", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(transcribe_router)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")