import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from metiscode.tool import ToolContext, create_bash_tool

T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:  # noqa: UP047
    return asyncio.run(coro)


def _context(asked: list[tuple[str, list[str]]]) -> ToolContext:
    async def ask(permission: str, patterns: list[str]) -> None:
        asked.append((permission, patterns))

    def metadata(_payload: dict[str, object]) -> None:
        return None

    return ToolContext(
        session_id="sess_1",
        message_id="msg_1",
        agent="general",
        abort=asyncio.Event(),
        metadata=metadata,
        ask=ask,
    )


def test_echo_hello_outputs_text() -> None:
    tool = create_bash_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    result = _run(instance.execute({"command": "echo hello"}, _context(asked)))

    assert "hello" in result.output.lower()
    assert result.metadata["exit_code"] == 0


def test_timeout_returns_timeout_output() -> None:
    tool = create_bash_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    result = _run(
        instance.execute(
            {"command": "Start-Sleep -Seconds 2", "timeout": 100},
            _context(asked),
        )
    )

    assert result.metadata["timed_out"] is True
    assert "timed out" in result.output.lower()


def test_permission_ask_receives_command_prefix_pattern() -> None:
    tool = create_bash_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    _ = _run(instance.execute({"command": "git status"}, _context(asked)))

    assert asked
    permission, patterns = asked[0]
    assert permission == "bash"
    assert patterns == ["git *"]


def test_stderr_is_captured_in_output() -> None:
    tool = create_bash_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    result = _run(
        instance.execute(
            {"command": "Write-Error 'oops'"},
            _context(asked),
        )
    )

    assert "oops" in result.output.lower()


def test_windows_shell_routing_cmd_vs_powershell() -> None:
    tool = create_bash_tool()
    instance = _run(tool.init("general"))

    asked_cmd: list[tuple[str, list[str]]] = []
    cmd_result = _run(instance.execute({"command": "dir"}, _context(asked_cmd)))
    assert cmd_result.metadata["shell"] == "cmd"

    asked_ps: list[tuple[str, list[str]]] = []
    ps_result = _run(
        instance.execute(
            {"command": "Get-Process | Select-Object -First 1"},
            _context(asked_ps),
        )
    )
    assert ps_result.metadata["shell"] == "powershell"
