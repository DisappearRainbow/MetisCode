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
