"""Minimal SQLite persistence for sessions and notes. Stdlib sqlite3 only."""

import os
import sqlite3
import uuid
from datetime import datetime, timezone

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    consent INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('recording', 'draft', 'approved')),
    transcript TEXT
);
CREATE TABLE IF NOT EXISTS notes (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id),
    draft TEXT,
    edited TEXT,
    approved TEXT
);
"""


def default_db_path() -> str:
    return os.environ.get("SCRIBE_DB_PATH", "data/scribe.db")


def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or default_db_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(_SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_session(db_path: str | None = None) -> dict:
    session_id = uuid.uuid4().hex[:12]
    created_at = _now()
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO sessions (id, created_at, consent, status) VALUES (?, ?, 1, 'recording')",
            (session_id, created_at),
        )
    return {"id": session_id, "created_at": created_at, "consent": True, "status": "recording"}


def finish_session(session_id: str, transcript: str, db_path: str | None = None) -> dict | None:
    with connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE sessions SET transcript = ?, status = 'draft' WHERE id = ?",
            (transcript, session_id),
        )
        if cur.rowcount == 0:
            return None
    return get_session(session_id, db_path)


def save_note_draft(session_id: str, draft: str, db_path: str | None = None) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO notes (session_id, draft) VALUES (?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET draft = excluded.draft",
            (session_id, draft),
        )


def save_note_edit(session_id: str, edited: str, db_path: str | None = None) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO notes (session_id, edited) VALUES (?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET edited = excluded.edited",
            (session_id, edited),
        )


def approve_note(session_id: str, approved: str, db_path: str | None = None) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE sessions SET status = 'approved' WHERE id = ?", (session_id,))
        conn.execute(
            "INSERT INTO notes (session_id, approved) VALUES (?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET approved = excluded.approved",
            (session_id, approved),
        )


def get_session(session_id: str, db_path: str | None = None) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT s.id, s.created_at, s.consent, s.status, s.transcript, "
            "n.draft, n.edited, n.approved "
            "FROM sessions s LEFT JOIN notes n ON n.session_id = s.id "
            "WHERE s.id = ?",
            (session_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def list_sessions(db_path: str | None = None) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, created_at, consent, status FROM sessions ORDER BY created_at DESC, rowid DESC"
        ).fetchall()
    return [dict(row) for row in rows]
