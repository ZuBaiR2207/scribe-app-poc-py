import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.notes.generator import NoteGenerationError

client = TestClient(app)


class FakeGenerator:
    def __init__(self, note="draft", error=None):
        self.note = note
        self.error = error

    def generate(self, transcript):
        if self.error is not None:
            raise self.error
        return self.note


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "test.db")
    from app import db as db_module

    db_module.init_db(path)
    monkeypatch.setattr(app.state, "db_path", path, raising=False)
    return path


def make_session():
    response = client.post("/api/sessions")
    assert response.status_code == 200
    return response.json()["id"]


def test_create_session_returns_recording(db_path):
    response = client.post("/api/sessions")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "recording"
    assert body["consent"] is True


def test_full_lifecycle(db_path, monkeypatch):
    monkeypatch.setattr(app.state, "note_generator", FakeGenerator(note="the draft"), raising=False)
    sid = make_session()

    finished = client.post(f"/api/sessions/{sid}/finish", json={"transcript": "  hello  "})
    assert finished.status_code == 200
    assert finished.json()["status"] == "draft"
    assert finished.json()["transcript"] == "hello"

    noted = client.post(f"/api/sessions/{sid}/note")
    assert noted.status_code == 200
    assert noted.json()["draft"] == "the draft"

    edited = client.patch(f"/api/sessions/{sid}/note", json={"note": "my edit"})
    assert edited.status_code == 200
    assert edited.json()["edited"] == "my edit"

    approved = client.post(f"/api/sessions/{sid}/approve")
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "approved"
    assert body["approved"] == "my edit"


def test_approve_without_note_conflicts(db_path):
    sid = make_session()
    client.post(f"/api/sessions/{sid}/finish", json={"transcript": "hello"})
    # no note generated: approve must 409
    response = client.post(f"/api/sessions/{sid}/approve")
    assert response.status_code == 409


def test_note_on_recording_session_conflicts(db_path):
    sid = make_session()
    response = client.post(f"/api/sessions/{sid}/note")
    assert response.status_code == 409


def test_note_generation_503_when_not_configured(db_path, monkeypatch):
    monkeypatch.setattr(app.state, "note_generator", None, raising=False)
    sid = make_session()
    client.post(f"/api/sessions/{sid}/finish", json={"transcript": "hello"})
    response = client.post(f"/api/sessions/{sid}/note")
    assert response.status_code == 503


def test_note_generation_502_on_generator_error(db_path, monkeypatch):
    error = NoteGenerationError("LLM request failed (RateLimitError)")
    monkeypatch.setattr(app.state, "note_generator", FakeGenerator(error=error), raising=False)
    sid = make_session()
    client.post(f"/api/sessions/{sid}/finish", json={"transcript": "hello"})
    response = client.post(f"/api/sessions/{sid}/note")
    assert response.status_code == 502
    assert "RateLimitError" in response.json()["detail"]


def test_edit_rejected_after_approval(db_path, monkeypatch):
    monkeypatch.setattr(app.state, "note_generator", FakeGenerator(note="d"), raising=False)
    sid = make_session()
    client.post(f"/api/sessions/{sid}/finish", json={"transcript": "hello"})
    client.post(f"/api/sessions/{sid}/note")
    client.post(f"/api/sessions/{sid}/approve")
    response = client.patch(f"/api/sessions/{sid}/note", json={"note": "new text"})
    assert response.status_code == 409


def test_unknown_session_404(db_path):
    assert client.get("/api/sessions/nope").status_code == 404
    assert client.post("/api/sessions/nope/finish", json={"transcript": "x"}).status_code == 404
    assert client.patch("/api/sessions/nope/note", json={"note": "x"}).status_code == 404
    assert client.post("/api/sessions/nope/approve").status_code == 404
    assert client.post("/api/sessions/nope/note").status_code == 404


def test_list_sessions(db_path):
    sid = make_session()
    response = client.get("/api/sessions")
    assert response.status_code == 200
    ids = [row["id"] for row in response.json()]
    assert sid in ids


def test_blank_transcript_rejected_on_finish(db_path):
    sid = make_session()
    response = client.post(f"/api/sessions/{sid}/finish", json={"transcript": "   "})
    assert response.status_code == 422
