"""WebSocket handler: 16 kHz PCM in, live partial/final text out."""

import asyncio
import json
import logging
import time

import numpy as np
from fastapi import WebSocket, WebSocketDisconnect

from app.config import Settings
from app.speech.engine import SpeechEngine
from app.speech.segmenter import SAMPLE_RATE, SegmenterConfig, UtteranceSegmenter

logger = logging.getLogger(__name__)

MIN_PARTIAL_AUDIO_S = 0.8


def to_float32(pcm: np.ndarray) -> np.ndarray:
    return pcm.astype(np.float32) / 32768.0


async def handle_transcription(
    websocket: WebSocket,
    engine: SpeechEngine,
    settings: Settings,
    language: str | None,
) -> None:
    await websocket.accept()

    segmenter = UtteranceSegmenter(
        SegmenterConfig(
            min_rms=settings.vad_min_rms,
            noise_multiplier=settings.vad_noise_multiplier,
            end_silence_ms=settings.vad_end_silence_ms,
            min_speech_ms=settings.vad_min_speech_ms,
            max_utterance_s=settings.vad_max_utterance_s,
        )
    )
    queue: asyncio.Queue[np.ndarray | None] = asyncio.Queue()
    state = {"connected": True}

    async def safe_send(payload: dict) -> bool:
        try:
            await websocket.send_json(payload)
            return True
        except Exception:
            return False

    async def receive_audio() -> None:
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    state["connected"] = False
                    return
                data = message.get("bytes")
                if data:
                    if len(data) % 2:
                        data = data[:-1]
                    for utterance in segmenter.feed(np.frombuffer(data, dtype=np.int16)):
                        queue.put_nowait(utterance)
                    continue
                text = message.get("text")
                if text:
                    try:
                        command = json.loads(text)
                    except ValueError:
                        continue
                    if command.get("type") == "stop":
                        leftover = segmenter.flush()
                        if leftover is not None:
                            queue.put_nowait(leftover)
                        return
        except (WebSocketDisconnect, RuntimeError):
            state["connected"] = False
        finally:
            queue.put_nowait(None)

    async def send_partial() -> None:
        if not state["connected"] or not segmenter.in_speech:
            return
        audio = segmenter.current_audio()
        if len(audio) < MIN_PARTIAL_AUDIO_S * SAMPLE_RATE:
            return
        try:
            result = await asyncio.to_thread(engine.transcribe, to_float32(audio), language, True)
        except Exception:
            logger.exception("partial transcription failed")
            return
        if result.text and segmenter.in_speech:
            await safe_send({"type": "partial", "text": result.text})

    async def send_final(audio: np.ndarray) -> None:
        started = time.perf_counter()
        try:
            result = await asyncio.to_thread(engine.transcribe, to_float32(audio), language, False)
        except Exception:
            logger.exception("final transcription failed")
            await safe_send({"type": "error", "message": "Transcription failed for one segment."})
            return
        processing = time.perf_counter() - started
        audio_seconds = len(audio) / SAMPLE_RATE
        logger.info("utterance: audio=%.1fs processing=%.1fs", audio_seconds, processing)
        await safe_send(
            {
                "type": "final",
                "text": result.text,
                "language": result.language,
                "audio_seconds": audio_seconds,
                "processing_seconds": processing,
            }
        )

    async def transcribe_loop() -> None:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=settings.partial_interval_s)
            except TimeoutError:
                await send_partial()
                continue
            if item is None:
                await safe_send({"type": "done"})
                return
            if state["connected"]:
                await send_final(item)

    receiver = asyncio.create_task(receive_audio())
    worker = asyncio.create_task(transcribe_loop())
    results = await asyncio.gather(receiver, worker, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            logger.error("websocket task failed: %s", type(result).__name__)

    try:
        await websocket.close()
    except Exception:
        pass