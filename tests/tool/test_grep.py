import asyncio
import fnmatch
from collections.abc import Awaitable
from pathlib import Path
from typing import TypeVar

import pytest

from metiscode.tool import ToolContext, create_grep_tool

T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:  # noqa: UP047
    return asyncio.run(coro)


def _install_virtual_tree(monkeypatch: pytest.MonkeyPatch, files: dict[Path, str]) -> None:
    normalized = {str(path.resolve()): content for path, content in files.items()}

    def _fake_is_file(self: Path) -> bool:
        return str(self.resolve()) in normalized

    def _fake_read_text(self: Path, encoding: str = "utf-8") -> str:
        _ = encoding
        key = str(self.resolve())
        if key not in normalized:
            raise FileNotFoundError(key)
        return normalized[key]

    def _fake_rglob(self: Path, pattern: str):  # type: ignore[no-untyped-def]
        root = self.resolve()
        for path_str in normalized:
            file_path = Path(path_str)
            try:
                relative = file_path.relative_to(root)
            except ValueError:
                continue
            if fnmatch.fnmatch(str(relative), pattern):
                yield file_path

    monkeypatch.setattr(Path, "is_file", _fake_is_file)
    monkeypatch.setattr(Path, "read_text", _fake_read_text)
    monkeypatch.setattr(Path, "rglob", _fake_rglob)


def _context(
    asked: list[tuple[str, list[str]]],
    *,
    directory: Path,
    worktree: str | None = None,
) -> ToolContext:
    async def ask(permission: str, patterns: list[str]) -> None:
        asked.append((permission, patterns))

    def metadata(_payload: dict[str, object]) -> None:
        return None

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


def test_grep_finds_regex_matches() -> None:
    root = (Path(".").resolve() / "virtual_project").resolve()
    files = {
        (root / "a.py").resolve(): "def one():\n    pass\n",
        (root / "b.txt").resolve(): "hello\n",
        (root / "sub" / "c.py").resolve(): "def two():\n    return 1\n",
    }

    monkeypatch = pytest.MonkeyPatch()
    _install_virtual_tree(monkeypatch, files)
    try:
        tool = create_grep_tool()
        instance = _run(tool.init("general"))
        asked: list[tuple[str, list[str]]] = []
        result = _run(instance.execute({"pattern": r"def \w+"}, _context(asked, directory=root)))
    finally:
        monkeypatch.undo()

    assert f"{(root / 'a.py').resolve()}:1:def one():" in result.output
    assert f"{(root / 'sub' / 'c.py').resolve()}:1:def two():" in result.output
    assert asked[0] == ("grep", [r"def \w+"])


def test_grep_include_filters_extensions() -> None:
    root = (Path(".").resolve() / "virtual_project").resolve()
    files = {
        (root / "a.py").resolve(): "alpha token\n",
        (root / "b.txt").resolve(): "alpha token\n",
    }

    monkeypatch = pytest.MonkeyPatch()
    _install_virtual_tree(monkeypatch, files)
    try:
        tool = create_grep_tool()
        instance = _run(tool.init("general"))
        asked: list[tuple[str, list[str]]] = []
        result = _run(
            instance.execute(
                {"pattern": "alpha", "include": "*.py"},
                _context(asked, directory=root),
            )
        )
    finally:
        monkeypatch.undo()

    assert str((root / "a.py").resolve()) in result.output
    assert str((root / "b.txt").resolve()) not in result.output


def test_grep_returns_no_files_when_no_match() -> None:
    root = (Path(".").resolve() / "virtual_project").resolve()
    files = {
        (root / "a.py").resolve(): "beta\n",
    }

    monkeypatch = pytest.MonkeyPatch()
    _install_virtual_tree(monkeypatch, files)
    try:
        tool = create_grep_tool()
        instance = _run(tool.init("general"))
        asked: list[tuple[str, list[str]]] = []
        result = _run(instance.execute({"pattern": "alpha"}, _context(asked, directory=root)))
    finally:
        monkeypatch.undo()

    assert result.output == "No files found"
