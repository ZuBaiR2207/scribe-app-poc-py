"""Adapter: any OpenAI-compatible chat API (Gemini via AI Studio, Groq, OpenRouter, ...)."""

from openai import OpenAI, OpenAIError

from app.notes.generator import NoteGenerationError
from app.notes.prompt import build_messages


class OpenAICompatibleNoteGenerator:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 60.0,
        max_retries: int = 2,
        temperature: float = 0.2,
        reasoning_effort: str | None = None,
        client: OpenAI | None = None,
    ) -> None:
        self._client = client or OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout_s,
            max_retries=max_retries,
        )
        self._model = model
        self._temperature = temperature
        self._reasoning_effort = reasoning_effort

    def generate(self, transcript: str) -> str:
        extra: dict[str, str] = {}
        if self._reasoning_effort:
            extra["reasoning_effort"] = self._reasoning_effort
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=build_messages(transcript),
                temperature=self._temperature,
                **extra,
            )
        except OpenAIError as exc:
            # Only the error type is reported: never the prompt, transcript or key.
            raise NoteGenerationError(f"LLM request failed ({type(exc).__name__})") from exc

        if not response.choices:
            raise NoteGenerationError("LLM returned no result")
        content = response.choices[0].message.content or ""
        if not content.strip():
            raise NoteGenerationError("LLM returned an empty note")
        return content.strip()
