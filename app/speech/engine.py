"""Speech engine port: anything that can turn 16 kHz audio into text."""

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class Transcription:
    text: str
    language: str


class SpeechEngine(Protocol):
    def transcribe(
        self, audio: np.ndarray, language: str | None, fast: bool = False
    ) -> Transcription:
        """Transcribe mono float32 audio (16 kHz, values -1..1).

        language: a code such as "en", or None to auto-detect.
        fast: trade accuracy for speed (used for live partial text).
        """
        ...
