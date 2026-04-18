from __future__ import annotations

import asyncio

import pytest

from metiscode.session import SessionDB
from tests.integration.e2e_utils import (
    e2e_db_path,
    e2e_dir,
    parse_session_id,
    require_e2e_env,
    run_metiscode,
)

pytestmark = pytest.mark.e2e


def test_e2e_persistence_check11() -> None:
    require_e2e_env()
    workdir = e2e_dir("e2e-persistence")
    first = run_metiscode(
        [
            "run",
            "--model",
            "deepseek:deepseek-chat",
            "remember: my favorite color is purple",
        ],
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
            "deepseek:deepseek-chat",
            "what is my favorite color?",
        ],
        cwd=workdir,
    )
    assert second.returncode == 0
    assert "purple" in second.stdout.lower()


def test_e2e_subagent_task_check9() -> None:
    require_e2e_env()
    workdir = e2e_dir("e2e-subagent")
    result = run_metiscode(
        [
            "run",
            "--model",
            "deepseek:deepseek-chat",
            (
                "MUST call task tool exactly once first. "
                "Use subagent_type=general, description='check9', "
                "prompt='read pyproject.toml and return package name'. "
                "After tool_result, answer briefly."
            ),
        ],
        cwd=workdir,
        timeout=90.0,
    )
    assert result.returncode == 0
    session_id = parse_session_id(result.stdout)
    assert session_id
    assert "task_id:" in result.stdout

    db = SessionDB(project_id="global", db_path=e2e_db_path(workdir))
    asyncio.run(db.init())
    sessions = asyncio.run(db.list_sessions())
    children = [item for item in sessions if item.get("parent_id") == session_id]
    assert children, f"expected child sessions under {session_id}, got none"
