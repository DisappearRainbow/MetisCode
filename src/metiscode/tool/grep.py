"""Grep tool for regex content search."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from metiscode.project.service import contains_path
from metiscode.tool.tool import ToolContext, ToolInfo, ToolResult, define

_SKIP_DIRS = {".git", "node_modules", "__pycache__"}
_RESULT_LIMIT = 100


class GrepParams(BaseModel):
    """Parameters for grep tool."""

    model_config = ConfigDict(extra="forbid")
    pattern: str
    path: str | None = None
    include: str | None = None
    context: int = Field(default=2, ge=0)


def _resolve_workspace(ctx: ToolContext) -> tuple[Path, str]:
    base_directory = Path(".").resolve()
    worktree = "/"
    if not isinstance(ctx.extra, dict):
        return base_directory, worktree

    directory = ctx.extra.get("directory")
    if isinstance(directory, str) and directory.strip():
        base_directory = Path(directory).resolve()

    worktree_input = ctx.extra.get("worktree")
    if isinstance(worktree_input, str) and worktree_input.strip():
        worktree = worktree_input

    return base_directory, worktree


def _under_skipped_dir(path: Path) -> bool:
    return any(part in _SKIP_DIRS for part in path.parts)


def _iter_files(search_root: Path, include: str | None) -> list[Path]:
    files: list[Path] = []
    for path in search_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(search_root)
        if _under_skipped_dir(relative):
            continue
        if include and not fnmatch.fnmatch(str(relative), include):
            continue
        files.append(path.resolve())
    return files


async def _execute_grep(params: GrepParams, ctx: ToolContext) -> ToolResult:
    await ctx.ask("grep", [params.pattern])

    base_directory, worktree = _resolve_workspace(ctx)
    search_root = (
        Path(params.path).resolve()
        if params.path and Path(params.path).is_absolute()
        else (base_directory / (params.path or ".")).resolve()
    )
    in_scope = contains_path(
        directory=str(base_directory),
        worktree=worktree,
        filepath=str(search_root),
    )
    if not in_scope:
        await ctx.ask("external_directory", [str(search_root)])

    regex = re.compile(params.pattern)
    matches: list[tuple[Path, int, str]] = []
    for path in _iter_files(search_root, params.include):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        for index, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                matches.append((path, index, line))
                if len(matches) >= _RESULT_LIMIT:
                    break
        if len(matches) >= _RESULT_LIMIT:
            break

    if not matches:
        return ToolResult(
            title=params.pattern,
            output="No files found",
            metadata={"matches": 0, "truncated": False},
        )

    lines = [f"{path}:{line_number}:{line}" for path, line_number, line in matches]
    truncated = len(matches) >= _RESULT_LIMIT
    if truncated:
        lines.extend(["", f"(Results truncated: showing first {_RESULT_LIMIT} matches.)"])
    return ToolResult(
        title=params.pattern,
        output="\n".join(lines),
        metadata={"matches": len(matches), "truncated": truncated},
    )


def create_grep_tool() -> ToolInfo[GrepParams]:
    """Create grep tool definition."""
    return define(
        "grep",
        "Search file content by regex and print path:line:text matches.",
        GrepParams,
        _execute_grep,
    )
