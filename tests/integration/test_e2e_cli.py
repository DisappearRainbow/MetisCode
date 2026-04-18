from __future__ import annotations

import json

import pytest

from tests.integration.e2e_utils import e2e_dir, parse_session_id, require_e2e_env, run_metiscode

pytestmark = pytest.mark.e2e


def test_e2e_cli_basic_chat_check4() -> None:
    require_e2e_env()
    workdir = e2e_dir("cli-basic")
    result = run_metiscode(
        ["run", "--model", "deepseek:deepseek-chat", "say hello in one word"],
        cwd=workdir,
    )
    assert result.returncode == 0
    assert result.stdout.strip()


def test_e2e_cli_create_file_check5() -> None:
    require_e2e_env()
    workdir = e2e_dir("cli-create")
    result = run_metiscode(
        ["run", "--model", "deepseek:deepseek-chat", "create hello.py that prints hi"],
        cwd=workdir,
    )
    assert result.returncode == 0
    file_path = workdir / "hello.py"
    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert "print" in content and "hi" in content


def test_e2e_cli_edit_file_check6() -> None:
    require_e2e_env()
    workdir = e2e_dir("cli-edit")
    file_path = workdir / "hello.py"
    file_path.write_text("print('hi')\n", encoding="utf-8")
    result = run_metiscode(
        [
            "run",
            "--model",
            "deepseek:deepseek-chat",
            "edit hello.py to add a greet function",
        ],
        cwd=workdir,
    )
    assert result.returncode == 0
    content = file_path.read_text(encoding="utf-8")
    assert "greet" in content


def test_e2e_cli_permission_block_check10() -> None:
    require_e2e_env()
    workdir = e2e_dir("cli-permission-block")
    denied_file = workdir / "deny_me.py"
    result = run_metiscode(
        ["run", "--model", "deepseek:deepseek-chat", "create deny_me.py that prints hi"],
        cwd=workdir,
        env_overrides={
            "METISCODE_PERMISSION_RULES": json.dumps({"edit": {"*": "deny"}}),
        },
    )
    combined = f"{result.stdout}\n{result.stderr}".lower()
    assert result.returncode != 0 or "[tool:error]" in result.stdout
    assert (
        "permission denied: edit:" in combined
        or "no completed tool call was recorded" in combined
    )
    assert not denied_file.exists()


def test_e2e_cli_model_switch_check12() -> None:
    require_e2e_env()
    workdir = e2e_dir("cli-model-switch")
    first = run_metiscode(
        ["run", "--model", "deepseek:deepseek-chat", "remember this token: abc123"],
        cwd=workdir,
    )
    assert first.returncode == 0
    session_id = parse_session_id(first.stdout)
    assert session_id

    second = run_metiscode(
        [
            "run",
            "--session-id",
            session_id,
            "--model",
            "deepseek:deepseek-reasoner",
            "repeat the token",
        ],
        cwd=workdir,
    )
    assert second.returncode == 0
    assert second.stdout.strip()
