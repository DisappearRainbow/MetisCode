import asyncio
from pathlib import Path

from click.testing import CliRunner

import metiscode.cli.main as cli_module
from metiscode.permission import Rule
from metiscode.session import SessionDB
from metiscode.util.dotenv import load_dotenv as real_load_dotenv
from metiscode.util.errors import PermissionDeniedError
from metiscode.util.ids import ulid_str


def _local_db_path(name: str) -> Path:
    base = Path(".").resolve() / ".metiscode" / "tmp" / "cli"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{name}.db"


def test_cli_help_contains_expected_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "serve" in result.output
    assert "session" in result.output
    assert "tui" in result.output


def test_cli_run_parses_model_option(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_run_prompt(  # type: ignore[no-untyped-def]
        model: str,
        agent: str,
        session_id: str | None,
        prompt: str,
    ) -> str:
        assert model == "anthropic:claude-sonnet-4-20250514"
        assert agent == "build"
        assert session_id is None
        assert prompt == "hello"
        return "sess_test"

    monkeypatch.setattr(cli_module, "_run_prompt", fake_run_prompt)
    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        ["run", "--model", "anthropic:claude-sonnet-4-20250514", "hello"],
    )
    assert result.exit_code == 0
    assert "model=anthropic:claude-sonnet-4-20250514" in result.output


def test_cli_session_list_empty_database_outputs_empty_list(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    base = Path(".").resolve() / ".metiscode" / "tmp"
    base.mkdir(parents=True, exist_ok=True)
    db = SessionDB(project_id="global", db_path=base / "cli_test_list.db")

    def fake_db() -> SessionDB:
        return db

    monkeypatch.setattr(cli_module, "_db", fake_db)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["session", "list"])
    assert result.exit_code == 0
    assert result.output.strip() == "[]"


def test_cli_serve_invokes_uvicorn_with_factory(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, object] = {}

    def fake_run(app: str, **kwargs: object) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr(cli_module.uvicorn, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["serve", "--host", "127.0.0.1", "--port", "4096"])
    assert result.exit_code == 0
    assert captured["app"] == "metiscode.server.app:create_app"
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 4096
    assert captured["factory"] is True
    assert captured["log_level"] == "info"
    assert captured["reload"] is False


def test_cli_serve_reload_flag_passes_true(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, object] = {}

    def fake_run(app: str, **kwargs: object) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr(cli_module.uvicorn, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["serve", "--reload"])
    assert result.exit_code == 0
    assert captured["app"] == "metiscode.server.app:create_app"
    assert captured["reload"] is True


def test_contains_file_action_hint_handles_cn_and_en() -> None:
    assert cli_module._contains_file_action_hint("请创建 hello.py") is True
    assert cli_module._contains_file_action_hint("Please create hello.py") is True
    assert cli_module._contains_file_action_hint("just chat with me") is False


def test_echo_assistant_parts_tracks_claim_and_tool_completion() -> None:
    parts = [
        {"data": {"type": "text", "content": "我将创建 hello.py 并写入内容。"}},
        {"data": {"type": "tool", "tool_id": "write", "state": "completed", "output": "ok"}},
    ]
    stats = cli_module._echo_assistant_parts(parts)
    assert stats.has_text is True
    assert stats.has_tool is True
    assert stats.has_completed_tool is True
    assert stats.claims_file_action is True


def test_should_fail_claimed_file_action_only_before_any_success() -> None:
    claim_only = cli_module.AssistantTurnStats(
        has_text=True,
        has_tool=False,
        has_completed_tool=False,
        schema_claims_file_action=True,
        claims_file_action=True,
    )
    assert (
        cli_module._should_fail_claimed_file_action(
            stats=claim_only,
            has_any_completed_tool=False,
        )
        is True
    )
    assert (
        cli_module._should_fail_claimed_file_action(
            stats=claim_only,
            has_any_completed_tool=True,
        )
        is False
    )


def test_should_warn_requested_file_action_only_before_any_success() -> None:
    no_tool = cli_module.AssistantTurnStats(
        has_text=True,
        has_tool=False,
        has_completed_tool=False,
        claims_file_action=False,
    )
    assert (
        cli_module._should_warn_requested_file_action(
            prompt_requests_file_action=True,
            stats=no_tool,
            has_any_completed_tool=False,
        )
        is True
    )
    assert (
        cli_module._should_warn_requested_file_action(
            prompt_requests_file_action=True,
            stats=no_tool,
            has_any_completed_tool=True,
        )
        is False
    )


def test_run_compaction_then_retry_succeeds(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    db = SessionDB(project_id="global", db_path=_local_db_path("cli_compaction_ok"))
    call_counter = {"value": 0}
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeAgentInfo:
        max_steps = 3
        permission = []

    class _FakeAgentService:
        def get(self, _agent: str) -> _FakeAgentInfo:
            return _FakeAgentInfo()

    class _FakeProcessor:
        def __init__(self, *, session_id: str, assistant_message_id: str, db: SessionDB) -> None:
            self.session_id = session_id
            self.assistant_message_id = assistant_message_id
            self.db = db

        async def process(self, _stream_input) -> str:  # type: ignore[no-untyped-def]
            call_counter["value"] += 1
            if call_counter["value"] == 1:
                return "compact"
            await self.db.create_part(
                part_id=ulid_str(),
                message_id=self.assistant_message_id,
                session_id=self.session_id,
                part_type="text",
                data={"type": "text", "content": "done"},
            )
            return "stop"

    def fake_db() -> SessionDB:
        return db

    def fake_create(  # type: ignore[no-untyped-def]
        *,
        session_id,
        assistant_message_id,
        model,
        agent,
        abort,
        llm,
        registry,
        db,
        bus,
    ):
        _ = (model, agent, abort, llm, registry, bus)
        assert db is not None
        return _FakeProcessor(
            session_id=session_id,
            assistant_message_id=assistant_message_id,
            db=db,
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

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["run", "--model", "openai:gpt-4.1", "hello"])
    assert result.exit_code == 0
    assert "[compacted]" in result.output

    session_line = next(
        line for line in result.output.splitlines() if line.startswith("session_id=")
    )
    session_id = session_line.split("=", 1)[1]
    messages = asyncio.run(db.get_messages(session_id))
    message_ids = [str(item["id"]) for item in messages]
    parts = []
    for message_id in message_ids:
        parts.extend(asyncio.run(db.get_message_parts(message_id)))
    assert any(part["data"].get("type") == "compaction" for part in parts)


def test_run_compaction_twice_raises_click_exception(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    db = SessionDB(project_id="global", db_path=_local_db_path("cli_compaction_twice"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeAgentInfo:
        max_steps = 3
        permission = []

    class _FakeAgentService:
        def get(self, _agent: str) -> _FakeAgentInfo:
            return _FakeAgentInfo()

    class _FakeProcessor:
        async def process(self, _stream_input) -> str:  # type: ignore[no-untyped-def]
            return "compact"

    def fake_db() -> SessionDB:
        return db

    def fake_create(**_kwargs):  # type: ignore[no-untyped-def]
        return _FakeProcessor()

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

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["run", "--model", "openai:gpt-4.1", "hello"])
    assert result.exit_code != 0
    assert "context overflow persists after compaction" in result.output


def test_run_deepseek_without_credentials_fails_early(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(cli_module, "load_dotenv", lambda path=None: None)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["run", "--model", "deepseek:deepseek-chat", "hello"])
    assert result.exit_code != 0
    assert "DEEPSEEK_API_KEY" in result.output


def test_run_deepseek_uses_dotenv_credentials(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    db = SessionDB(project_id="global", db_path=_local_db_path("cli_deepseek_dotenv"))
    env_path = _local_db_path("dotenv-source").with_suffix(".env")
    env_path.write_text("DEEPSEEK_API_KEY=sk-fake\n", encoding="utf-8")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

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

        async def process(self, _stream_input) -> str:  # type: ignore[no-untyped-def]
            await self.db.create_part(
                part_id=ulid_str(),
                message_id=self.assistant_message_id,
                session_id=self.session_id,
                part_type="text",
                data={"type": "text", "content": "ok"},
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
    monkeypatch.setattr(cli_module, "load_dotenv", lambda path=None: real_load_dotenv(env_path))

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["run", "--model", "deepseek:deepseek-chat", "hello"])
    assert result.exit_code == 0


def test_cli_tui_serve_starts_server_and_runs_app(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    records: dict[str, object] = {"terminated": False}

    class _FakeProcess:
        def terminate(self) -> None:
            records["terminated"] = True

    class _FakeApp:
        def __init__(self, *, base_url: str) -> None:
            records["base_url"] = base_url

        def run(self) -> None:
            records["app_run"] = True

    def fake_popen(args):  # type: ignore[no-untyped-def]
        records["popen_args"] = args
        return _FakeProcess()

    def fake_wait(base_url: str) -> None:
        records["wait_base_url"] = base_url

    monkeypatch.setattr(cli_module, "_find_free_port", lambda: 43123)
    monkeypatch.setattr(cli_module, "_wait_for_server", fake_wait)
    monkeypatch.setattr(cli_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(cli_module, "MetiscodeApp", _FakeApp)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["tui", "--serve"])
    assert result.exit_code == 0
    assert records["base_url"] == "http://127.0.0.1:43123"
    assert records["wait_base_url"] == "http://127.0.0.1:43123"
    assert records["app_run"] is True
    assert records["terminated"] is True
    assert isinstance(records["popen_args"], list)


def test_cli_tui_no_serve_uses_given_base_url(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    records: dict[str, object] = {"popen_called": False}

    class _FakeApp:
        def __init__(self, *, base_url: str) -> None:
            records["base_url"] = base_url

        def run(self) -> None:
            records["app_run"] = True

    def fake_popen(args):  # type: ignore[no-untyped-def]
        records["popen_called"] = True
        records["popen_args"] = args
        raise AssertionError("Popen should not be called when --no-serve")

    monkeypatch.setattr(cli_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(cli_module, "MetiscodeApp", _FakeApp)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        ["tui", "--no-serve", "--base-url", "http://x:8000"],
    )
    assert result.exit_code == 0
    assert records["popen_called"] is False
    assert records["base_url"] == "http://x:8000"
    assert records["app_run"] is True


def test_load_runtime_permission_rules_parses_json_object(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("METISCODE_PERMISSION_RULES", '{"edit":{"*":"deny"}}')
    rules = cli_module._load_runtime_permission_rules()
    assert rules == [Rule(permission="edit", pattern="*", action="deny")]


def test_build_permission_ask_blocks_deny_rule() -> None:
    ask = cli_module._build_permission_ask(
        [Rule(permission="edit", pattern="*", action="deny")]
    )

    async def _run() -> None:
        await ask("edit", ["hello.py"])

    try:
        asyncio.run(_run())
    except PermissionDeniedError as error:
        assert "Permission denied: edit:hello.py" in str(error)
    else:
        raise AssertionError("expected PermissionDeniedError")


def test_extract_assistant_status_strips_marker_and_parses_schema() -> None:
    text = 'answer body\nMETISCODE_STATUS: {"file_action":"planned"}'
    sanitized, status = cli_module._extract_assistant_status(text)
    assert sanitized == "answer body"
    assert status is not None
    assert status.file_action == "planned"


def test_should_fail_claimed_file_action_uses_schema_claim_only() -> None:
    legacy_keyword_claim = cli_module.AssistantTurnStats(
        has_text=True,
        claims_file_action=True,
        schema_claims_file_action=False,
    )
    schema_claim = cli_module.AssistantTurnStats(
        has_text=True,
        claims_file_action=True,
        schema_claims_file_action=True,
    )
    assert (
        cli_module._should_fail_claimed_file_action(
            stats=legacy_keyword_claim,
            has_any_completed_tool=False,
        )
        is False
    )
    assert (
        cli_module._should_fail_claimed_file_action(
            stats=schema_claim,
            has_any_completed_tool=False,
        )
        is True
    )


def test_should_warn_requested_file_action_suppressed_by_tool_error() -> None:
    no_tool_with_error = cli_module.AssistantTurnStats(
        has_text=True,
        has_tool=True,
        has_completed_tool=False,
        has_error_tool=True,
    )
    assert (
        cli_module._should_warn_requested_file_action(
            prompt_requests_file_action=True,
            stats=no_tool_with_error,
            has_any_completed_tool=False,
            has_any_error_tool=False,
        )
        is False
    )


def test_build_turn_system_prompt_contains_status_schema() -> None:
    system_prompt = cli_module._build_turn_system_prompt("build")
    assert system_prompt.startswith("Agent: build")
    assert "METISCODE_STATUS" in system_prompt


def test_echo_assistant_parts_extracts_permission_denied_error() -> None:
    parts = [
        {
            "data": {
                "type": "tool",
                "tool_id": "write",
                "state": "error",
                "error": "Permission denied: edit:hello.py (matched deny rule)",
            }
        }
    ]
    stats = cli_module._echo_assistant_parts(parts)
    assert stats.has_tool is True
    assert stats.has_error_tool is True
    assert stats.permission_denied_error is not None
