import asyncio
from pathlib import Path

import metiscode.cli.main as cli_module
from metiscode.permission import Rule, evaluate
from metiscode.session import SessionDB
from metiscode.util.ids import ulid_str


def test_session_persistence_across_reopen() -> None:
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


def test_run_prompt_with_session_id_reuses_history(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    db_path = (
        Path(".").resolve() / ".metiscode" / "tmp" / "integration" / "session_resume_history.db"
    )
    db = SessionDB(project_id="global", db_path=db_path)
    captured_messages: list[list[dict[str, object]]] = []
    call_counter = {"value": 0}

    class _FakeAgentInfo:
        max_steps = 1
        permission = []

    class _FakeAgentService:
        def get(self, _agent: str) -> _FakeAgentInfo:
            return _FakeAgentInfo()

    class _FakeProcessor:
        def __init__(self, *, session_id: str, assistant_message_id: str, db: SessionDB) -> None:
            self.session_id = session_id
            self.assistant_message_id = assistant_message_id
            self.db = db

        async def process(self, stream_input) -> str:  # type: ignore[no-untyped-def]
            captured_messages.append(stream_input.messages)
            call_counter["value"] += 1
            response = "OK alpha" if call_counter["value"] == 1 else "OK remember"
            await self.db.create_part(
                part_id=ulid_str(),
                message_id=self.assistant_message_id,
                session_id=self.session_id,
                part_type="text",
                data={"type": "text", "content": response},
            )
            return "stop"

    def fake_db() -> SessionDB:
        return db

    def fake_create(**kwargs):  # type: ignore[no-untyped-def]
        return _FakeProcessor(
            session_id=kwargs["session_id"],
            assistant_message_id=kwargs["assistant_message_id"],
            db=kwargs["db"],
        )

    async def fake_tool_schemas(  # type: ignore[no-untyped-def]
        registry,
        *,
        agent: str,
        provider: str,
    ) -> list[dict[str, object]]:
        _ = (registry, agent, provider)
        return []

    monkeypatch.setattr(cli_module, "_db", fake_db)
    monkeypatch.setattr(cli_module, "AgentService", lambda: _FakeAgentService())
    monkeypatch.setattr(cli_module, "_tool_schemas", fake_tool_schemas)
    monkeypatch.setattr(cli_module.SessionProcessor, "create", staticmethod(fake_create))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    first_session_id = asyncio.run(
        cli_module._run_prompt(
            model="openai:gpt-4.1",
            agent="build",
            session_id=None,
            prompt="alpha",
        )
    )
    second_session_id = asyncio.run(
        cli_module._run_prompt(
            model="openai:gpt-4.1",
            agent="build",
            session_id=first_session_id,
            prompt="what did you just say",
        )
    )

    assert second_session_id == first_session_id
    assert len(captured_messages) == 2
    second_messages = captured_messages[1]
    assert any(
        item.get("role") == "user" and "alpha" in str(item.get("content", ""))
        for item in second_messages
    )
    assert any(
        item.get("role") == "assistant" and "OK alpha" in str(item.get("content", ""))
        for item in second_messages
    )

    all_messages = asyncio.run(db.get_messages(first_session_id))
    assert len(all_messages) == 4
