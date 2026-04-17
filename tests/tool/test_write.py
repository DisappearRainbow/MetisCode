import asyncio
from collections.abc import Awaitable
from pathlib import Path
from typing import TypeVar

import pytest

from metiscode.tool import ToolContext, create_write_tool

T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:  # noqa: UP047
    return asyncio.run(coro)


def _install_virtual_fs(
    monkeypatch: pytest.MonkeyPatch,
    files: dict[Path, str],
) -> tuple[list[tuple[Path, bool, bool]], list[tuple[Path, str]]]:
    normalized = {str(path.resolve()): content for path, content in files.items()}
    mkdir_calls: list[tuple[Path, bool, bool]] = []
    write_calls: list[tuple[Path, str]] = []

    def _fake_exists(self: Path) -> bool:
        return str(self.resolve()) in normalized

    def _fake_read_text(self: Path, encoding: str = "utf-8") -> str:
        _ = encoding
        key = str(self.resolve())
        if key not in normalized:
            raise FileNotFoundError(key)
        return normalized[key]

    def _fake_write_text(self: Path, content: str, encoding: str = "utf-8") -> int:
        _ = encoding
        key = str(self.resolve())
        normalized[key] = content
        write_calls.append((self.resolve(), content))
        return len(content)

    def _fake_mkdir(self: Path, *, parents: bool = False, exist_ok: bool = False) -> None:
        mkdir_calls.append((self.resolve(), parents, exist_ok))

    monkeypatch.setattr(Path, "exists", _fake_exists)
    monkeypatch.setattr(Path, "read_text", _fake_read_text)
    monkeypatch.setattr(Path, "write_text", _fake_write_text)
    monkeypatch.setattr(Path, "mkdir", _fake_mkdir)

    return mkdir_calls, write_calls


def _context(
    asked: list[tuple[str, list[str]]],
    metadata_calls: list[dict[str, object]],
    *,
    directory: Path,
    worktree: str | None = None,
) -> ToolContext:
    async def ask(permission: str, patterns: list[str]) -> None:
        asked.append((permission, patterns))

    def metadata(payload: dict[str, object]) -> None:
        metadata_calls.append(payload)

    extra: dict[str, object] = {"directory": str(directory)}
    if worktree is not None:
        extra["worktree"] = worktree

    return ToolContext(
        session_id="sess_1",
        message_id="msg_1",
        agent="general",
        abort=asyncio.Event(),
        metadata=metadata,
        ask=ask,
        extra=extra,
    )


def test_writes_file_content(monkeypatch: pytest.MonkeyPatch) -> None:
    root = (Path(".").resolve() / "virtual_project").resolve()
    target = (root / "hello.txt").resolve()
    _, write_calls = _install_virtual_fs(monkeypatch, {})

    tool = create_write_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    metadata_calls: list[dict[str, object]] = []
    result = _run(
        instance.execute(
            {"file_path": str(target), "content": "hello world\n"},
            _context(asked, metadata_calls, directory=root),
        )
    )

    assert write_calls == [(target, "hello world\n")]
    assert result.output == "Created file successfully."
    assert asked[0][0] == "edit"
    assert metadata_calls


def test_creates_parent_directories_for_nested_path(monkeypatch: pytest.MonkeyPatch) -> None:
    root = (Path(".").resolve() / "virtual_project").resolve()
    target = (root / "a" / "b" / "c" / "d.txt").resolve()
    mkdir_calls, _ = _install_virtual_fs(monkeypatch, {})

    tool = create_write_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    metadata_calls: list[dict[str, object]] = []
    _ = _run(
        instance.execute(
            {"file_path": str(target), "content": "nested"},
            _context(asked, metadata_calls, directory=root),
        )
    )

    assert mkdir_calls
    assert mkdir_calls[0] == (target.parent, True, True)


def test_permission_ask_uses_relative_path_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    root = (Path(".").resolve() / "virtual_project").resolve()
    _install_virtual_fs(monkeypatch, {})

    tool = create_write_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    metadata_calls: list[dict[str, object]] = []
    _ = _run(
        instance.execute(
            {"file_path": "src/main.py", "content": "print('ok')\n"},
            _context(asked, metadata_calls, directory=root, worktree=str(root)),
        )
    )

    assert asked
    assert asked[0] == ("edit", [str(Path("src/main.py"))])
