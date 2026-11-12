from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SCRIBE_", extra="ignore")

    whisper_model: str = "small"
    whisper_compute_type: str = "int8"

    vad_min_rms: float = 400.0
    vad_noise_multiplier: float = 3.0
    vad_end_silence_ms: int = 700
    vad_min_speech_ms: int = 300
    vad_max_utterance_s: float = 20.0

    partial_interval_s: float = 1.5


@lru_cache
def get_settings() -> Settings:
    return Settings()