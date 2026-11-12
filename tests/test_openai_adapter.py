from types import SimpleNamespace

import pytest
from openai import OpenAIError

from app.notes.generator import NoteGenerationError
from app.notes.openai_compatible import OpenAICompatibleNoteGenerator


def make_client(content="  draft note  ", error=None, captured=None):
    def create(**kwargs):
        if captured is not None:
            captured.update(kwargs)
        if error is not None:
            raise error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def make_generator(client, reasoning_effort=None):
    return OpenAICompatibleNoteGenerator(
        base_url="http://unused",
        api_key="unused",
        model="test-model",
        reasoning_effort=reasoning_effort,
        client=client,
    )


def test_returns_stripped_note():
    assert make_generator(make_client()).generate("some transcript") == "draft note"


def test_empty_content_raises():
    with pytest.raises(NoteGenerationError):
        make_generator(make_client(content="   ")).generate("some transcript")


def test_sdk_error_is_wrapped_without_leaking_transcript():
    generator = make_generator(make_client(error=OpenAIError("boom")))
    with pytest.raises(NoteGenerationError) as exc_info:
        generator.generate("very private words")
    assert "very private words" not in str(exc_info.value)


def test_reasoning_effort_is_sent_only_when_set():
    captured = {}
    make_generator(make_client(captured=captured)).generate("x")
    assert "reasoning_effort" not in captured

    captured = {}
    make_generator(make_client(captured=captured), reasoning_effort="low").generate("x")
    assert captured["reasoning_effort"] == "low"
