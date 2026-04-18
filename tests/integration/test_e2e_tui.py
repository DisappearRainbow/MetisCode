from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
from urllib import error as urlerror
from urllib import request as urlrequest

import pytest
from textual.widgets import Markdown

from metiscode.tui import MessageList, MetiscodeApp
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


def test_e2e_tui_roundtrip_check8() -> None:
    require_e2e_env()
    workdir = e2e_dir("tui-roundtrip")
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

        async def scenario() -> None:
            app = MetiscodeApp(base_url=base_url, model="deepseek:deepseek-chat")
            async with app.run_test() as pilot:
                prompt = pilot.app.query_one("#prompt_input")
                prompt.focus()
                await pilot.press("s", "a", "y", " ", "h", "i", "enter")
                deadline = time.time() + 90
                message_list = pilot.app.query_one(MessageList)
                while time.time() < deadline:
                    if list(message_list.query(Markdown)):
                        break
                    await pilot.pause(0.2)
                else:
                    raise AssertionError("assistant text did not appear in message list")

                await pilot.press("ctrl+s")
                await pilot.press("escape")
                await pilot.press("ctrl+m")
                await pilot.press("escape")

        asyncio.run(scenario())
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
