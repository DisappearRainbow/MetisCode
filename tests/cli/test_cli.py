from pathlib import Path

from click.testing import CliRunner

import metiscode.cli.main as cli_module
from metiscode.session import SessionDB


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
