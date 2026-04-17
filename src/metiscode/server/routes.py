"""Server route handlers."""

from __future__ import annotations

from metiscode.session import SessionDB
from metiscode.util.ids import ulid_str


async def list_sessions(db: SessionDB) -> list[dict[str, object]]:
    await db.init()
    return await db.list_sessions()


async def get_session(db: SessionDB, session_id: str) -> dict[str, object] | None:
    await db.init()
    return await db.get_session(session_id)


async def create_session(
    db: SessionDB,
    *,
    model: str | None = None,
    agent: str | None = None,
) -> dict[str, object]:
    await db.init()
    session_id = ulid_str()
    await db.create_session(
        session_id=session_id,
        slug=f"session-{session_id[:6].lower()}",
        directory=".",
        title="New session",
    )
    return {"id": session_id, "model": model, "agent": agent}


async def post_message(db: SessionDB, session_id: str, content: str) -> dict[str, object]:
    if not content.strip():
        raise ValueError("content is required")
    await db.init()
    message_id = ulid_str()
    await db.create_message(
        message_id=message_id,
        session_id=session_id,
        role="user",
        data={"parts": [{"type": "text", "content": content}]},
    )
    return {"id": message_id, "session_id": session_id, "content": content}


async def get_messages(db: SessionDB, session_id: str) -> list[dict[str, object]]:
    await db.init()
    return await db.get_messages(session_id)


async def delete_session(db: SessionDB, session_id: str) -> dict[str, object]:
    await db.init()
    await db.delete_session(session_id)
    return {"deleted": session_id}


def health() -> dict[str, str]:
    return {"status": "ok"}
