from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import db
from app.api.notes import router as notes_router
from app.api.sessions import router as sessions_router
from app.api.transcribe_ws import router as transcribe_router
from app.config import get_settings
from app.notes.openai_compatible import OpenAICompatibleNoteGenerator
from app.speech.faster_whisper_engine import FasterWhisperEngine

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.engine = FasterWhisperEngine(settings.whisper_model, settings.whisper_compute_type)
    if settings.llm_configured:
        app.state.note_generator = OpenAICompatibleNoteGenerator(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
            model=settings.llm_model.strip(),
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            reasoning_effort=settings.llm_reasoning_effort.strip() or None,
        )
    else:
        app.state.note_generator = None
    db.init_db()
    app.state.db_path = db.default_db_path()
    yield


app = FastAPI(title="Wellness Scribe POC", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(transcribe_router)
app.include_router(notes_router)
app.include_router(sessions_router)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
