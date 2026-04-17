"""Bash-like shell tool for Windows."""

from __future__ import annotations

import asyncio
import re
import subprocess
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from metiscode.tool.tool import ToolContext, ToolInfo, ToolResult, define

_POWERSHELL_HINTS = (
    "Get-",
    "Set-",
    "Write-",
    "Start-",
    "Stop-",
    "$env:",
)


class BashParams(BaseModel):
    """Parameters for bash tool."""

    model_config = ConfigDict(extra="forbid")
    command: str
    timeout: int = Field(default=120_000, ge=1)
    description: str | None = None


def _split_command_segments(command: str) -> list[str]:
    return [segment.strip() for segment in re.split(r"\|\||&&|[|;]", command) if segment.strip()]


def _extract_permission_patterns(command: str) -> list[str]:
    patterns: list[str] = []
    for segment in _split_command_segments(command):
        parts = segment.split()
        if not parts:
            continue
        prefix = parts[0].strip().strip('"').strip("'")
        if not prefix:
            continue
        patterns.append(f"{prefix} *")
    return patterns


def _is_cd_only(command: str) -> bool:
    segments = _split_command_segments(command)
    if not segments:
        return False
    return all(segment.lower().startswith("cd ") or segment.lower() == "cd" for segment in segments)


def _pick_shell(command: str) -> tuple[str, Sequence[str]]:
    stripped = command.strip()
    starts_with_ps = stripped.lower().startswith("powershell ")
    has_ps_hint = any(hint in stripped for hint in _POWERSHELL_HINTS)
    if starts_with_ps or has_ps_hint:
        return "powershell", ["powershell", "-NoProfile", "-Command", command]
    return "cmd", ["cmd.exe", "/c", command]


async def _execute_bash(params: BashParams, ctx: ToolContext) -> ToolResult:
    patterns = _extract_permission_patterns(params.command)
    if patterns and not _is_cd_only(params.command):
        await ctx.ask("bash", patterns)

    shell_name, argv = _pick_shell(params.command)
    try:
        completed = await asyncio.to_thread(
            subprocess.run,
            list(argv),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            shell=False,
            timeout=params.timeout / 1000,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            title=params.description or "Bash",
            output=f"Command timed out after {params.timeout}ms",
            metadata={
                "shell": shell_name,
                "timed_out": True,
                "exit_code": None,
                "patterns": patterns,
            },
        )

    stdout_text = completed.stdout
    stderr_text = completed.stderr
    output = stdout_text
    if stderr_text:
        output = f"{output}\n{stderr_text}" if output else stderr_text

    return ToolResult(
        title=params.description or "Bash",
        output=output,
        metadata={
            "shell": shell_name,
            "timed_out": False,
            "exit_code": completed.returncode,
            "patterns": patterns,
        },
    )


def create_bash_tool() -> ToolInfo[BashParams]:
    """Build bash tool definition."""
    return define(
        "bash",
        "Run shell commands in cmd.exe or PowerShell on Windows.",
        BashParams,
        _execute_bash,
    )
