"""File write tool with permission checks and diff metadata."""

from __future__ import annotations

from difflib import unified_diff
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from metiscode.project.service import contains_path
from metiscode.tool.tool import ToolContext, ToolInfo, ToolResult, define


class WriteParams(BaseModel):
    """Parameters for write tool."""

    model_config = ConfigDict(extra="forbid")
    file_path: str
    content: str


def _resolve_path(file_path: str, base_directory: Path) -> Path:
    candidate = Path(file_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_directory / candidate).resolve()


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


def _permission_pattern(target: Path, base_directory: Path, worktree: str) -> str:
    if worktree != "/":
        try:
            return str(target.relative_to(Path(worktree).resolve()))
        except ValueError:
            return str(target)
    try:
        return str(target.relative_to(base_directory))
    except ValueError:
        return str(target)


def _build_diff(path_text: str, old_content: str, new_content: str) -> str:
    diff_lines = unified_diff(
        old_content.splitlines(),
        new_content.splitlines(),
        fromfile=path_text,
        tofile=path_text,
        lineterm="",
    )
    return "\n".join(diff_lines)


async def _execute_write(params: WriteParams, ctx: ToolContext) -> ToolResult:
    base_directory, worktree = _resolve_workspace(ctx)
    target = _resolve_path(params.file_path, base_directory)

    if not contains_path(directory=str(base_directory), worktree=worktree, filepath=str(target)):
        await ctx.ask("external_directory", [str(target.parent)])

    existed = target.exists()
    old_content = target.read_text(encoding="utf-8") if existed else ""
    diff = _build_diff(str(target), old_content, params.content)

    permission_pattern = _permission_pattern(target, base_directory, worktree)
    await ctx.ask("edit", [permission_pattern])
    ctx.metadata({"filepath": str(target), "diff": diff})

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(params.content, encoding="utf-8")

    return ToolResult(
        title=permission_pattern,
        output="Updated file successfully." if existed else "Created file successfully.",
        metadata={
            "path": str(target),
            "exists": existed,
            "diff": diff,
        },
    )


def create_write_tool() -> ToolInfo[WriteParams]:
    """Create write tool definition."""
    return define(
        "write",
        "Write full file content to path, creating directories as needed.",
        WriteParams,
        _execute_write,
    )

