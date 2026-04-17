import asyncio

from metiscode.permission import Rule, evaluate
from metiscode.session import SessionDB
from metiscode.util.ids import ulid_str


def test_session_persistence_across_reopen() -> None:
    from pathlib import Path

    db_path = Path(".").resolve() / ".metiscode" / "tmp" / "integration" / "lifecycle.db"
    db = SessionDB(project_id="global", db_path=db_path)
    asyncio.run(db.init())

    session_id = ulid_str()
    message_id = ulid_str()
    asyncio.run(db.create_session(session_id=session_id, slug="s", directory=".", title="t"))
    asyncio.run(
        db.create_message(
            message_id=message_id,
            session_id=session_id,
            role="user",
            data={"text": "hi"},
        )
    )

    reopened = SessionDB(project_id="global", db_path=db_path)
    asyncio.run(reopened.init())
    session = asyncio.run(reopened.get_session(session_id))
    messages = asyncio.run(reopened.get_messages(session_id))

    assert session is not None
    assert len(messages) == 1


def test_permission_blocking_denies_rm_command() -> None:
    rule = evaluate(
        "bash.run",
        "rm *",
        [Rule(permission="bash.run", pattern="rm *", action="deny")],
    )
    assert rule.action == "deny"
