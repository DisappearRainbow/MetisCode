import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from metiscode.tool import ToolContext, create_todo_tool

T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:  # noqa: UP047
    return asyncio.run(coro)


class _FakeTodoStore:
    def __init__(self) -> None:
        self.todos: list[dict[str, object]] = []

    async def get_todos(self, session_id: str) -> list[dict[str, object]]:
        return [todo for todo in self.todos if todo["session_id"] == session_id]

    async def create_todo(
        self,
        *,
        todo_id: str,
        session_id: str,
        content: str,
        status: str,
        priority: int,
    ) -> None:
        self.todos.append(
            {
                "id": todo_id,
                "session_id": session_id,
                "content": content,
                "status": status,
                "priority": priority,
            }
        )

    async def update_todo(self, todo_id: str, **fields: object) -> None:
        for todo in self.todos:
            if todo["id"] == todo_id:
                todo.update(fields)
                return


def _context(asked: list[tuple[str, list[str]]], store: _FakeTodoStore) -> ToolContext:
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
        extra={"todo_store": store},
    )


def test_todo_writes_items_to_store() -> None:
    tool = create_todo_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    store = _FakeTodoStore()
    result = _run(
        instance.execute(
            {
                "todos": [
                    {"content": "task a", "status": "pending", "priority": 1},
                    {"content": "task b", "status": "in_progress", "priority": 2},
                    {"content": "task c", "status": "done", "priority": 3},
                ]
            },
            _context(asked, store),
        )
    )

    assert len(store.todos) == 3
    assert result.title == "2 todos"
    assert asked[0] == ("todowrite", ["*"])


def test_todo_updates_existing_item_status() -> None:
    tool = create_todo_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    store = _FakeTodoStore()
    _run(
        instance.execute(
            {"todos": [{"content": "task a", "status": "pending", "priority": 1}]},
            _context(asked, store),
        )
    )
    _run(
        instance.execute(
            {"todos": [{"content": "task a", "status": "done", "priority": 5}]},
            _context(asked, store),
        )
    )

    assert len(store.todos) == 1
    assert store.todos[0]["status"] == "done"
    assert store.todos[0]["priority"] == 5

