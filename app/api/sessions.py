from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, StringConstraints

from app import db
from app.notes.generator import NoteGenerationError

router = APIRouter()

Transcript = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50000)
]
NoteText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50000)]


class FinishRequest(BaseModel):
    transcript: Transcript


class NoteEditRequest(BaseModel):
    note: NoteText


@router.post("/api/sessions")
def create_session(request: Request) -> dict:
    return db.create_session(request.app.state.db_path)


@router.get("/api/sessions")
def list_sessions(request: Request) -> list[dict]:
    return db.list_sessions(request.app.state.db_path)


@router.get("/api/sessions/{session_id}")
def get_session(session_id: str, request: Request) -> dict:
    session = db.get_session(session_id, request.app.state.db_path)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.post("/api/sessions/{session_id}/finish")
def finish_session(session_id: str, body: FinishRequest, request: Request) -> dict:
    session = db.finish_session(session_id, body.transcript, request.app.state.db_path)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.post("/api/sessions/{session_id}/note")
def generate_session_note(session_id: str, request: Request) -> dict:
    state = request.app.state
    session = db.get_session(session_id, state.db_path)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["status"] == "recording":
        raise HTTPException(status_code=409, detail="Session is still recording; finish it first.")
    if not session["transcript"]:
        raise HTTPException(status_code=409, detail="Session has no transcript.")
    generator = state.note_generator
    if generator is None:
        raise HTTPException(
            status_code=503,
            detail="LLM is not configured. Set SCRIBE_LLM_API_KEY and SCRIBE_LLM_MODEL in .env, then restart the server.",
        )
    try:
        draft = generator.generate(session["transcript"])
    except NoteGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    db.save_note_draft(session_id, draft, state.db_path)
    return db.get_session(session_id, state.db_path)


@router.patch("/api/sessions/{session_id}/note")
def edit_session_note(session_id: str, body: NoteEditRequest, request: Request) -> dict:
    session = db.get_session(session_id, request.app.state.db_path)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["status"] == "approved":
        raise HTTPException(status_code=409, detail="Note is approved and locked.")
    db.save_note_edit(session_id, body.note, request.app.state.db_path)
    return db.get_session(session_id, request.app.state.db_path)


@router.post("/api/sessions/{session_id}/approve")
def approve_session_note(session_id: str, request: Request) -> dict:
    session = db.get_session(session_id, request.app.state.db_path)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["status"] == "approved":
        raise HTTPException(status_code=409, detail="Note is already approved.")
    approved_text = session["edited"] or session["draft"]
    if not (approved_text or "").strip():
        raise HTTPException(status_code=409, detail="No note to approve; generate or edit one first.")
    db.approve_note(session_id, approved_text, request.app.state.db_path)
    return db.get_session(session_id, request.app.state.db_path)
