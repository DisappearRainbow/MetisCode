"""Task tool for subagent spawning stub."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict

from metiscode.session.message import SubtaskPart
from metiscode.tool.tool import ToolContext, ToolInfo, ToolResult, define
from metiscode.util.ids import ulid_str


class TaskParams(BaseModel):
    """Parameters for task tool."""

    model_config = ConfigDict(extra="forbid")
    description: str
    prompt: str
    subagent_type: str | None = None
    task_id: str | None = None


class TaskDBProtocol(Protocol):
    """DB protocol for task session creation."""

    async def create_session(self, **fields: object) -> None: ...


async def _execute_task(params: TaskParams, ctx: ToolContext) -> ToolResult:
    subagent_type = params.subagent_type or "general"
    await ctx.ask("task", [subagent_type])

    task_session_id = params.task_id or ulid_str()
    db: TaskDBProtocol | None = None
    if isinstance(ctx.extra, dict):
        maybe_db = ctx.extra.get("db")
        if maybe_db is not None and hasattr(maybe_db, "create_session"):
            db = cast(TaskDBProtocol, maybe_db)
        if db is not None and params.task_id is None:
            await db.create_session(
                session_id=task_session_id,
                slug=f"task-{task_session_id[:6].lower()}",
                directory=str(ctx.extra.get("directory") or "."),
                title=f"{params.description} (@{subagent_type} subagent)",
                parent_id=ctx.session_id,
            )

    runner: Callable[[TaskParams, ToolContext], Awaitable[str]] | None = None
    if isinstance(ctx.extra, dict):
        maybe_runner = ctx.extra.get("task_runner")
        if callable(maybe_runner):
            runner = cast(Callable[[TaskParams, ToolContext], Awaitable[str]], maybe_runner)

    result_text = await runner(params, ctx) if runner else "Subtask queued."
    subtask_part = SubtaskPart(session_id=task_session_id, description=params.description)
    return ToolResult(
        title=params.description,
        output=f"task_id: {task_session_id}\n\n<task_result>\n{result_text}\n</task_result>",
        metadata={
            "session_id": task_session_id,
            "subagent_type": subagent_type,
            "subtask_part": subtask_part.model_dump(),
        },
    )


def create_task_tool() -> ToolInfo[TaskParams]:
    """Create task tool definition."""
    return define(
        "task",
        "Spawn or resume subagent task sessions.",
        TaskParams,
        _execute_task,
    )
