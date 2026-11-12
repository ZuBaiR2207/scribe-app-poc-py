"""Energy-based voice activity detection that cuts a 16 kHz PCM stream into utterances."""

from collections import deque
from dataclasses import dataclass

import numpy as np

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 480 samples per frame


@dataclass(frozen=True)
class SegmenterConfig:
    min_rms: float = 400.0          # quietest loudness that can count as speech
    noise_multiplier: float = 3.0   # speech must be this much louder than background noise
    end_silence_ms: int = 700       # this much silence ends an utterance
    min_speech_ms: int = 300        # shorter bursts are ignored as noise
    max_utterance_s: float = 20.0   # force a cut after this long
    pre_roll_ms: int = 200          # keep this much audio from before speech starts


class UtteranceSegmenter:
    def __init__(self, config: SegmenterConfig | None = None) -> None:
        self._cfg = config or SegmenterConfig()
        self._pending = np.zeros(0, dtype=np.int16)  # samples that do not fill a frame yet
        self._pre_roll: deque[np.ndarray] = deque(
            maxlen=max(1, self._cfg.pre_roll_ms // FRAME_MS)
        )
        self._utterance: list[np.ndarray] = []
        self._in_speech = False
        self._speech_frames = 0
        self._silence_frames = 0
        self._noise_floor = 0.0

    @property
    def in_speech(self) -> bool:
        return self._in_speech

    def current_audio(self) -> np.ndarray:
        """Audio of the utterance in progress (empty if none)."""
        if not self._utterance:
            return np.zeros(0, dtype=np.int16)
        return np.concatenate(self._utterance)

    def feed(self, samples: np.ndarray) -> list[np.ndarray]:
        """Add int16 samples. Returns the utterances that finished (int16 arrays)."""
        finished: list[np.ndarray] = []
        data = np.concatenate([self._pending, samples.astype(np.int16, copy=False)])
        frame_count = len(data) // FRAME_SAMPLES
        for i in range(frame_count):
            frame = data[i * FRAME_SAMPLES : (i + 1) * FRAME_SAMPLES]
            utterance = self._process_frame(frame)
            if utterance is not None:
                finished.append(utterance)
        self._pending = data[frame_count * FRAME_SAMPLES :]
        return finished

    def flush(self) -> np.ndarray | None:
        """Finish any utterance still in progress (call when the stream ends)."""
        if not self._in_speech:
            return None
        return self._finish()

    def _process_frame(self, frame: np.ndarray) -> np.ndarray | None:
        rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
        threshold = max(self._cfg.min_rms, self._cfg.noise_multiplier * self._noise_floor)
        is_speech = rms > threshold
        if not is_speech:
            self._noise_floor = 0.95 * self._noise_floor + 0.05 * rms

        if not self._in_speech:
            if is_speech:
                self._in_speech = True
                self._utterance = list(self._pre_roll)
                self._utterance.append(frame)
                self._pre_roll.clear()
                self._speech_frames = 1
                self._silence_frames = 0
            else:
                self._pre_roll.append(frame)
            return None

        self._utterance.append(frame)
        if is_speech:
            self._speech_frames += 1
            self._silence_frames = 0
        else:
            self._silence_frames += 1

        ended = self._silence_frames * FRAME_MS >= self._cfg.end_silence_ms
        too_long = len(self._utterance) * FRAME_MS >= self._cfg.max_utterance_s * 1000
        if ended or too_long:
            return self._finish()
        return None

    def _finish(self) -> np.ndarray | None:
        speech_ms = self._speech_frames * FRAME_MS
        audio = np.concatenate(self._utterance) if self._utterance else None
        self._utterance = []
        self._in_speech = False
        self._speech_frames = 0
        self._silence_frames = 0
        if audio is None or speech_ms < self._cfg.min_speech_ms:
            return None
        return audio