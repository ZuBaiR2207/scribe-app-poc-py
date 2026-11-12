import pytest

from app import db


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    db.init_db(path)
    return path


def test_create_and_finish_session(db_path):
    session = db.create_session(db_path)
    assert session["status"] == "recording"
    assert session["consent"] is True

    finished = db.finish_session(session["id"], "hello transcript", db_path)
    assert finished["status"] == "draft"
    assert finished["transcript"] == "hello transcript"


def test_finish_missing_session_returns_none(db_path):
    assert db.finish_session("nope", "text", db_path) is None


def test_note_lifecycle(db_path):
    session = db.create_session(db_path)
    sid = session["id"]
    db.finish_session(sid, "transcript", db_path)

    db.save_note_draft(sid, "draft note", db_path)
    row = db.get_session(sid, db_path)
    assert row["draft"] == "draft note"

    db.save_note_edit(sid, "edited note", db_path)
    row = db.get_session(sid, db_path)
    assert row["edited"] == "edited note"

    db.approve_note(sid, "edited note", db_path)
    row = db.get_session(sid, db_path)
    assert row["status"] == "approved"
    assert row["approved"] == "edited note"


def test_list_sessions_orders_newest_first(db_path):
    first = db.create_session(db_path)
    second = db.create_session(db_path)
    rows = db.list_sessions(db_path)
    assert [r["id"] for r in rows] == [second["id"], first["id"]]


def test_get_missing_session(db_path):
    assert db.get_session("nope", db_path) is None
