from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from urllib import error as urlerror
from urllib import request as urlrequest

import httpx
import pytest

from tests.integration.e2e_utils import e2e_dir, require_e2e_env

pytestmark = pytest.mark.e2e


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_health(base_url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    url = f"{base_url}/health"
    while time.time() < deadline:
        try:
            with urlrequest.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except (urlerror.URLError, TimeoutError):
            time.sleep(0.2)
    raise AssertionError("server did not become healthy")


def test_e2e_server_flow_check7() -> None:
    require_e2e_env()
    workdir = e2e_dir("server-flow")
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["METISCODE_DB_PATH"] = str((workdir / "e2e.db").resolve())
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "metiscode",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=workdir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_health(base_url)
        with httpx.Client(base_url=base_url, timeout=30.0) as client:
            created = client.post(
                "/session",
                json={"model": "deepseek:deepseek-chat", "agent": "build"},
            )
            created.raise_for_status()
            session_id = created.json()["id"]

            posted = client.post(
                f"/session/{session_id}/message",
                json={"content": "hello", "model": "deepseek:deepseek-chat", "agent": "build"},
            )
            assert posted.status_code == 202

            deadline = time.time() + 45
            while time.time() < deadline:
                messages = client.get(f"/session/{session_id}/message")
                messages.raise_for_status()
                payload = messages.json()
                has_assistant = (
                    isinstance(payload, list)
                    and any(item.get("role") == "assistant" for item in payload)
                )
                if has_assistant:
                    break
                time.sleep(0.5)
            else:
                raise AssertionError("assistant message not observed within timeout")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
