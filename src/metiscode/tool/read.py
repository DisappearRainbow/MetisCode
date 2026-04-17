"""File read tool with optional slicing and line-number formatting."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from metiscode.project.service import contains_path
from metiscode.tool.tool import ToolContext, ToolInfo, ToolResult, define


class ReadParams(BaseModel):
    """Parameters for read tool."""

    model_config = ConfigDict(extra="forbid")
    file_path: str
    offset: int | None = Field(default=None, ge=0)
    limit: int | None = Field(default=None, ge=0)


def _resolve_path(file_path: str, base_directory: Path) -> Path:
    candidate = Path(file_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_directory / candidate).resolve()


async def _execute_read(params: ReadParams, ctx: ToolContext) -> ToolResult:
    base_directory = Path(".").resolve()
    worktree = "/"
    if isinstance(ctx.extra, dict):
        directory = ctx.extra.get("directory")
        if isinstance(directory, str) and directory.strip():
            base_directory = Path(directory).resolve()
        worktree_input = ctx.extra.get("worktree")
        if isinstance(worktree_input, str) and worktree_input.strip():
            worktree = worktree_input

    target = _resolve_path(params.file_path, base_directory)
    if not contains_path(directory=str(base_directory), worktree=worktree, filepath=str(target)):
        await ctx.ask("external_directory", [str(target.parent)])

    text = target.read_text(encoding="utf-8")
    lines = text.splitlines()
    offset = params.offset or 0
    if params.limit is None:
        selected = lines[offset:]
    else:
        selected = lines[offset : offset + params.limit]

    output = "\n".join(f"{offset + index + 1}\t{line}" for index, line in enumerate(selected))
    return ToolResult(
        title=f"Read {target.name}",
        output=output,
        metadata={
            "path": str(target),
            "offset": offset,
            "limit": params.limit,
            "line_count": len(selected),
        },
    )


def create_read_tool() -> ToolInfo[ReadParams]:
    """Create read tool definition."""
    return define(
        "read",
        "Read file content with line numbers and optional offset/limit.",
        ReadParams,
        _execute_read,
    )

