from fastapi import APIRouter, WebSocket

from app.config import get_settings
from app.speech.ws_handler import handle_transcription

router = APIRouter()

# UI value -> language code for Whisper (None = auto-detect)
ALLOWED_LANGUAGES: dict[str, str | None] = {
    "auto": None,
    "en": "en",
    "ms": "ms",
    "zh": "zh",
    "ta": "ta",
}


@router.websocket("/ws/transcribe")
async def transcribe_socket(websocket: WebSocket, language: str = "auto") -> None:
    if language not in ALLOWED_LANGUAGES:
        await websocket.close(code=1008)
        return
    await handle_transcription(
        websocket,
        websocket.app.state.engine,
        get_settings(),
        ALLOWED_LANGUAGES[language],
    )
