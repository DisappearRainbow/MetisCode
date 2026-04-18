import asyncio
import tempfile
from collections.abc import Awaitable
from pathlib import Path
from typing import TypeVar

from metiscode.session.db import SessionDB, default_db_path

T = TypeVar("T")

def _run(coro: Awaitable[T]) -> T:  # noqa: UP047
    return asyncio.run(coro)


def _new_db(project_id: str) -> SessionDB:
    base = Path.home() / ".codex" / "memories"
    base.mkdir(parents=True, exist_ok=True)
    db_file = Path(tempfile.mkstemp(prefix="metiscode-db-", suffix=".sqlite3", dir=base)[1])
    return SessionDB(project_id=project_id, db_path=db_file)


def test_create_session_and_get_session_roundtrip() -> None:
    db = _new_db("proj_a")
    _run(db.init())
    _run(
        db.create_session(
            session_id="sess_1",
            slug="hello",
            directory="C:/repo",
            title="First",
            permission={"bash": {"*": "ask"}},
        )
    )
    session = _run(db.get_session("sess_1"))
    assert session is not None
    assert session["id"] == "sess_1"
    assert session["project_id"] == "proj_a"
    assert session["permission"] == {"bash": {"*": "ask"}}


def test_create_message_associated_with_session() -> None:
    db = _new_db("proj_a")
    _run(db.init())
    _run(db.create_session(session_id="sess_1", slug="s", directory="C:/repo", title="T"))
    _run(
        db.create_message(
            message_id="msg_1",
            session_id="sess_1",
            role="user",
            data={"text": "hi"},
        )
    )

    messages = _run(db.get_messages("sess_1"))
    assert len(messages) == 1
    assert messages[0]["id"] == "msg_1"
    assert messages[0]["data"] == {"text": "hi"}


def test_create_part_associated_with_message() -> None:
    db = _new_db("proj_a")
    _run(db.init())
    _run(db.create_session(session_id="sess_1", slug="s", directory="C:/repo", title="T"))
    _run(
        db.create_message(
            message_id="msg_1",
            session_id="sess_1",
            role="assistant",
            data={"ok": True},
        )
    )
    _run(
        db.create_part(
            part_id="part_1",
            message_id="msg_1",
            session_id="sess_1",
            part_type="text",
            data={"content": "hello"},
        )
    )

    parts = _run(db.get_message_parts("msg_1"))
    assert len(parts) == 1
    assert parts[0]["id"] == "part_1"
    assert parts[0]["data"] == {"content": "hello"}


def test_list_sessions_filters_by_project() -> None:
    db_a = _new_db("proj_a")
    _run(db_a.init())
    _run(db_a.create_session(session_id="a1", slug="a1", directory="C:/a", title="A1"))

    db_b = _new_db("proj_b")
    _run(db_b.init())
    _run(db_b.create_session(session_id="b1", slug="b1", directory="C:/b", title="B1"))

    sessions_a = _run(db_a.list_sessions("proj_a"))
    sessions_b = _run(db_b.list_sessions("proj_b"))
    assert [item["id"] for item in sessions_a] == ["a1"]
    assert [item["id"] for item in sessions_b] == ["b1"]


def test_delete_session_cascades_messages_and_parts() -> None:
    db = _new_db("proj_a")
    _run(db.init())
    _run(db.create_session(session_id="sess_1", slug="s", directory="C:/repo", title="T"))
    _run(
        db.create_message(
            message_id="msg_1",
            session_id="sess_1",
            role="assistant",
            data={"ok": True},
        )
    )
    _run(
        db.create_part(
            part_id="part_1",
            message_id="msg_1",
            session_id="sess_1",
            part_type="text",
            data={"content": "hello"},
        )
    )
    _run(db.delete_session("sess_1"))

    assert _run(db.get_session("sess_1")) is None
    assert _run(db.get_messages("sess_1")) == []
    assert _run(db.get_message_parts("msg_1")) == []


def test_data_json_roundtrip() -> None:
    db = _new_db("proj_a")
    _run(db.init())
    _run(db.create_session(session_id="sess_1", slug="s", directory="C:/repo", title="T"))
    payload = {"nested": {"list": [1, 2, 3], "ok": True}}
    _run(db.create_message(message_id="msg_1", session_id="sess_1", role="user", data=payload))

    message = _run(db.get_messages("sess_1"))[0]
    assert message["data"] == payload


def test_default_db_path_respects_env_override(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    override = Path(".").resolve() / ".metiscode" / "tmp" / "env-db.sqlite3"
    monkeypatch.setenv("METISCODE_DB_PATH", str(override))
    assert default_db_path("global") == override.resolve()
