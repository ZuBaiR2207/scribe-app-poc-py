from fastapi.testclient import TestClient

from app.main import app
from app.notes.generator import NoteGenerationError

# No "with" block: server startup (which loads the Whisper model) is not run in tests.
client = TestClient(app)


class FakeGenerator:
    def __init__(self, note="draft", error=None):
        self.note = note
        self.error = error
        self.received = None

    def generate(self, transcript):
        self.received = transcript
        if self.error is not None:
            raise self.error
        return self.note


def install(monkeypatch, generator):
    monkeypatch.setattr(app.state, "note_generator", generator, raising=False)


def test_returns_503_when_llm_not_configured(monkeypatch):
    install(monkeypatch, None)
    response = client.post("/api/notes/generate", json={"transcript": "hello"})
    assert response.status_code == 503


def test_blank_transcript_is_rejected(monkeypatch):
    install(monkeypatch, FakeGenerator())
    response = client.post("/api/notes/generate", json={"transcript": "   "})
    assert response.status_code == 422


def test_missing_transcript_is_rejected(monkeypatch):
    install(monkeypatch, FakeGenerator())
    response = client.post("/api/notes/generate", json={})
    assert response.status_code == 422


def test_success_returns_note(monkeypatch):
    fake = FakeGenerator(note="the note")
    install(monkeypatch, fake)
    response = client.post("/api/notes/generate", json={"transcript": "  hello  "})
    assert response.status_code == 200
    assert response.json() == {"note": "the note"}
    assert fake.received == "hello"


def test_generator_failure_returns_502(monkeypatch):
    error = NoteGenerationError("LLM request failed (RateLimitError)")
    install(monkeypatch, FakeGenerator(error=error))
    response = client.post("/api/notes/generate", json={"transcript": "hello"})
    assert response.status_code == 502
    assert "RateLimitError" in response.json()["detail"]
