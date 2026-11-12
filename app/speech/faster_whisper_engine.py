"""Adapter: faster-whisper running locally on CPU."""

import threading

import numpy as np
from faster_whisper import WhisperModel

from app.speech.engine import Transcription


class FasterWhisperEngine:
    def __init__(self, model_name: str, compute_type: str = "int8") -> None:
        self._model = WhisperModel(model_name, device="cpu", compute_type=compute_type)
        self._lock = threading.Lock()  # one transcription at a time

    def transcribe(
        self, audio: np.ndarray, language: str | None, fast: bool = False
    ) -> Transcription:
        with self._lock:
            segments, info = self._model.transcribe(
                audio,
                language=language,
                beam_size=1 if fast else 5,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            # `segments` is lazy: the real work happens while we loop over it.
            text = " ".join(segment.text.strip() for segment in segments).strip()
        return Transcription(text=text, language=info.language)
