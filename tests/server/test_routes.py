import asyncio
from pathlib import Path

import pytest

from metiscode.server import routes
from metiscode.session import SessionDB


def _db(path_name: str) -> SessionDB:
    base = Path(".").resolve() / ".metiscode" / "tmp"
    base.mkdir(parents=True, exist_ok=True)
    return SessionDB(project_id="global", db_path=base / path_name)


def test_list_sessions_returns_empty() -> None:
    db = _db("routes.db")
    sessions = asyncio.run(routes.list_sessions(db))
    assert sessions == []


def test_create_session_returns_id() -> None:
    db = _db("routes2.db")
    created = asyncio.run(routes.create_session(db))
    assert "id" in created


def test_health_returns_ok() -> None:
    assert routes.health() == {"status": "ok"}


def test_post_message_without_content_raises() -> None:
    db = _db("routes3.db")
    created = asyncio.run(routes.create_session(db))
    with pytest.raises(ValueError):
        asyncio.run(routes.post_message(db, created["id"], ""))
