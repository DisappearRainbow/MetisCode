import asyncio
import shutil
from pathlib import Path

from metiscode.llm import TextDelta
from metiscode.provider import ProviderService
from metiscode.session import SessionDB, SessionProcessor, StreamInput, is_overflow, prune
from metiscode.tool import ToolRegistry, create_edit_tool, create_task_tool, create_write_tool
from metiscode.util.ids import ulid_str


class _FakeLLM:
    def __init__(self, events: list[object]) -> None:
        self.events = events

    async def stream(self, **_kwargs):  # type: ignore[no-untyped-def]
        for event in self.events:
            yield event


class _Bus:
    async def publish(self, _event: object, _payload: object) -> None:
        return None


def _db_path(name: str) -> Path:
    base = Path(".").resolve() / ".metiscode" / "tmp" / "integration"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{name}.db"


def test_basic_chat_flow_writes_user_assistant_parts() -> None:
    db = SessionDB(project_id="global", db_path=_db_path("basic_chat"))
    session_id = ulid_str()
    asyncio.run(db.init())
    asyncio.run(db.create_session(session_id=session_id, slug="s", directory=".", title="t"))
    message_id = ulid_str()
    asyncio.run(
        db.create_message(
            message_id=message_id,
            session_id=session_id,
            role="assistant",
            data={},
        )
    )

    processor = SessionProcessor.create(
        session_id=session_id,
        assistant_message_id=message_id,
        model="openai:gpt-4.1",
        agent="build",
        abort=asyncio.Event(),
        llm=_FakeLLM([TextDelta(content="hello")]),  # type: ignore[arg-type]
        registry=ToolRegistry(),
        db=db,
        bus=_Bus(),
    )
    result = asyncio.run(
        processor.process(StreamInput(model="openai:gpt-4.1", messages=[], tools=[], system=""))
    )
    assert result == "stop"
    parts = asyncio.run(db.get_message_parts(message_id))
    assert any(item["data"]["content"] == "hello" for item in parts)  # type: ignore[index]


def test_tool_execution_write_then_edit_changes_file() -> None:
    root = Path(".").resolve() / ".metiscode" / "tmp" / "integration" / "files"
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

    registry = ToolRegistry()
    registry.register(create_write_tool())  # type: ignore[arg-type]
    registry.register(create_edit_tool())  # type: ignore[arg-type]

    async def run_tool(tool_name: str, params: str) -> None:
        info = registry.get(tool_name)
        assert info is not None
        instance = await info.init("build")
        from metiscode.tool import ToolContext

        await instance.execute(
            __import__("json").loads(params),
            ToolContext(
                session_id="s",
                message_id="m",
                agent="build",
                abort=asyncio.Event(),
                metadata=lambda _payload: None,
                ask=lambda _permission, _patterns: asyncio.sleep(0),
                extra={"directory": str(root), "worktree": str(root)},
            ),
        )

    asyncio.run(
        run_tool(
            "write",
            '{"file_path":"hello.py","content":"print(\\"hi\\")\\n"}',
        )
    )
    asyncio.run(
        run_tool(
            "edit",
            '{"file_path":"hello.py","old_string":"print(\\"hi\\")","new_string":"print(\\"hello\\")"}',
        )
    )
    assert (root / "hello.py").read_text(encoding="utf-8") == 'print("hello")\n'


def test_compaction_trigger_on_small_context_limit() -> None:
    service = ProviderService()
    model = service.get_model("anthropic", "claude-sonnet-4-20250514")
    assert is_overflow(180_000, model) is True


def test_subagent_spawn_creates_child_session() -> None:
    db = SessionDB(project_id="global", db_path=_db_path("subagent_spawn"))
    asyncio.run(db.init())
    parent = ulid_str()
    asyncio.run(db.create_session(session_id=parent, slug="p", directory=".", title="parent"))

    tool = create_task_tool()
    instance = asyncio.run(tool.init("build"))
    from metiscode.tool import ToolContext

    result = asyncio.run(
        instance.execute(
            {"description": "subtask", "prompt": "do"},
            ToolContext(
                session_id=parent,
                message_id="m1",
                agent="build",
                abort=asyncio.Event(),
                metadata=lambda _payload: None,
                ask=lambda _permission, _patterns: asyncio.sleep(0),
                extra={"db": db, "directory": "."},
            ),
        )
    )
    assert "task_id:" in result.output


def test_compaction_prune_marks_old_tool_output() -> None:
    db = SessionDB(project_id="global", db_path=_db_path("compaction_prune"))
    asyncio.run(db.init())
    session_id = ulid_str()
    asyncio.run(db.create_session(session_id=session_id, slug="s", directory=".", title="t"))
    message_id = ulid_str()
    asyncio.run(
        db.create_message(
            message_id=message_id,
            session_id=session_id,
            role="assistant",
            data={},
        )
    )
    asyncio.run(
        db.create_part(
            part_id=ulid_str(),
            message_id=message_id,
            session_id=session_id,
            part_type="tool",
            data={
                "type": "tool",
                "tool_id": "x",
                "state": "completed",
                "input": {},
                "output": "y" * 300000,
            },
        )
    )
    model = ProviderService().get_model("anthropic", "claude-sonnet-4-20250514")
    asyncio.run(prune(session_id, model, db))
    parts = asyncio.run(db.get_message_parts(message_id))
    assert any(part["data"].get("type") == "compaction" for part in parts)  # type: ignore[union-attr]
