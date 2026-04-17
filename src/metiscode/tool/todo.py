"""Todo write tool."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from metiscode.tool.tool import ToolContext, ToolInfo, ToolResult, define
from metiscode.util.ids import ulid_str

TodoStatus = Literal["pending", "in_progress", "done"]


class TodoItem(BaseModel):
    """Single todo item."""

    model_config = ConfigDict(extra="forbid")
    content: str
    status: TodoStatus
    priority: int = Field(default=0, ge=0)


class TodoParams(BaseModel):
    """Parameters for todo tool."""

    model_config = ConfigDict(extra="forbid")
    todos: list[TodoItem]


class TodoStoreProtocol(Protocol):
    """Store protocol for todo persistence."""

    async def get_todos(self, session_id: str) -> list[dict[str, object]]: ...
    async def create_todo(
        self,
        *,
        todo_id: str,
        session_id: str,
        content: str,
        status: str,
        priority: int,
    ) -> None: ...
    async def update_todo(self, todo_id: str, **fields: object) -> None: ...


async def _execute_todo(params: TodoParams, ctx: ToolContext) -> ToolResult:
    await ctx.ask("todowrite", ["*"])
    store: TodoStoreProtocol | None = None
    if isinstance(ctx.extra, dict):
        maybe_store = ctx.extra.get("todo_store")
        if maybe_store is not None:
            store = maybe_store  # type: ignore[assignment]

    if store is not None:
        existing = await store.get_todos(ctx.session_id)
        by_content = {str(item["content"]): str(item["id"]) for item in existing}
        for todo in params.todos:
            todo_id = by_content.get(todo.content)
            if todo_id is None:
                await store.create_todo(
                    todo_id=ulid_str(),
                    session_id=ctx.session_id,
                    content=todo.content,
                    status=todo.status,
                    priority=todo.priority,
                )
            else:
                await store.update_todo(todo_id, status=todo.status, priority=todo.priority)

    pending_count = sum(1 for todo in params.todos if todo.status != "done")
    return ToolResult(
        title=f"{pending_count} todos",
        output="\n".join(
            f"- [{todo.status}] {todo.content} (p={todo.priority})"
            for todo in params.todos
        ),
        metadata={"todos": [todo.model_dump() for todo in params.todos]},
    )


def create_todo_tool() -> ToolInfo[TodoParams]:
    """Create todo write tool definition."""
    return define(
        "todowrite",
        "Write/update session todo list items.",
        TodoParams,
        _execute_todo,
    )

