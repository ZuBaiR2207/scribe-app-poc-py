from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, StringConstraints

from app.notes.generator import NoteGenerationError

router = APIRouter()

Transcript = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50000)
]


class NoteRequest(BaseModel):
    transcript: Transcript


class NoteResponse(BaseModel):
    note: str


@router.post("/api/notes/generate", response_model=NoteResponse)
def generate_note(body: NoteRequest, request: Request) -> NoteResponse:
    generator = request.app.state.note_generator
    if generator is None:
        raise HTTPException(
            status_code=503,
            detail="LLM is not configured. Set SCRIBE_LLM_API_KEY and SCRIBE_LLM_MODEL in .env, then restart the server.",
        )
    try:
        note = generator.generate(body.transcript)
    except NoteGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return NoteResponse(note=note)
