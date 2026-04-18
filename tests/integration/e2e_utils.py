from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


def require_e2e_env() -> None:
    if os.getenv("METISCODE_E2E") != "1":
        pytest.skip("set METISCODE_E2E=1 to run e2e tests")
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("set DEEPSEEK_API_KEY for real-provider e2e tests")


def e2e_dir(name: str) -> Path:
    base = Path(".").resolve() / ".metiscode" / "tmp" / "e2e"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def e2e_db_path(cwd: Path) -> Path:
    return (cwd / ".metiscode" / "e2e.db").resolve()


def run_metiscode(
    args: list[str],
    *,
    cwd: Path,
    timeout: float = 60.0,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("METISCODE_DB_PATH", str(e2e_db_path(cwd)))
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "metiscode", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def parse_session_id(stdout: str) -> str | None:
    for line in stdout.splitlines():
        if line.startswith("session_id="):
            return line.split("=", 1)[1].strip()
    return None
