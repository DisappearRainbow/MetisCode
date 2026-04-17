"""Glob tool for file pattern search."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from metiscode.project.service import contains_path
from metiscode.tool.tool import ToolContext, ToolInfo, ToolResult, define

_SKIP_DIRS = {".git", "node_modules", "__pycache__"}
_RESULT_LIMIT = 100


class GlobParams(BaseModel):
    """Parameters for glob tool."""

    model_config = ConfigDict(extra="forbid")
    pattern: str
    path: str | None = None


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


async def _execute_glob(params: GlobParams, ctx: ToolContext) -> ToolResult:
    await ctx.ask("glob", [params.pattern])

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

    matches: list[tuple[Path, float]] = []
    for path in search_root.glob(params.pattern):
        resolved = path.resolve()
        if not resolved.is_file():
            continue
        relative_path = resolved.relative_to(search_root) if resolved != search_root else resolved
        if _under_skipped_dir(relative_path):
            continue
        try:
            mtime = resolved.stat().st_mtime
        except OSError:
            mtime = 0.0
        matches.append((resolved, mtime))

    matches.sort(key=lambda item: item[1], reverse=True)
    truncated = len(matches) > _RESULT_LIMIT
    final_matches = matches[:_RESULT_LIMIT]

    if not final_matches:
        output = "No files found"
    else:
        lines = [str(path) for path, _mtime in final_matches]
        if truncated:
            lines.extend(
                [
                    "",
                    f"(Results are truncated: showing first {_RESULT_LIMIT} results.)",
                ]
            )
        output = "\n".join(lines)

    return ToolResult(
        title=str(search_root),
        output=output,
        metadata={"count": len(final_matches), "truncated": truncated},
    )


def create_glob_tool() -> ToolInfo[GlobParams]:
    """Create glob tool definition."""
    return define(
        "glob",
        "Find files matching glob patterns in a directory.",
        GlobParams,
        _execute_glob,
    )
