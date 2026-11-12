from functools import lru_cache

from pydantic import SecretStr
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

    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_api_key: SecretStr | None = None
    llm_model: str = ""
    llm_timeout_s: float = 60.0
    llm_max_retries: int = 2
    llm_reasoning_effort: str = ""

    @property
    def llm_configured(self) -> bool:
        key = self.llm_api_key.get_secret_value().strip() if self.llm_api_key is not None else ""
        return bool(key and self.llm_model.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
