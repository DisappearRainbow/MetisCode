import asyncio
import fnmatch
import os
from collections.abc import Awaitable
from pathlib import Path
from typing import TypeVar

import pytest

from metiscode.tool import ToolContext, create_glob_tool

T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:  # noqa: UP047
    return asyncio.run(coro)


def _install_virtual_tree(
    monkeypatch: pytest.MonkeyPatch,
    files: dict[Path, tuple[str, float]],
) -> None:
    normalized = {os.path.abspath(str(path)): data for path, data in files.items()}

    def _fake_is_file(self: Path) -> bool:
        return os.path.abspath(str(self)) in normalized

    def _fake_glob(self: Path, pattern: str):  # type: ignore[no-untyped-def]
        root = Path(os.path.abspath(str(self)))
        for path_str in normalized:
            file_path = Path(path_str)
            try:
                relative = file_path.relative_to(root)
            except ValueError:
                continue
            relative_text = str(relative)
            direct_match = fnmatch.fnmatch(relative_text, pattern)
            recursive_match = pattern.startswith("**/") and fnmatch.fnmatch(
                relative_text,
                pattern[3:],
            )
            if direct_match or recursive_match:
                yield file_path

    monkeypatch.setattr(Path, "is_file", _fake_is_file)
    monkeypatch.setattr(Path, "glob", _fake_glob)


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


def test_glob_matches_pattern() -> None:
    root = (Path(".").resolve() / "virtual_project").resolve()
    files = {
        (root / "a.py").resolve(): ("", 2.0),
        (root / "b.txt").resolve(): ("", 1.0),
        (root / "sub" / "c.py").resolve(): ("", 3.0),
    }

    monkeypatch = pytest.MonkeyPatch()
    _install_virtual_tree(monkeypatch, files)
    try:
        tool = create_glob_tool()
        instance = _run(tool.init("general"))
        asked: list[tuple[str, list[str]]] = []
        result = _run(instance.execute({"pattern": "**/*.py"}, _context(asked, directory=root)))
    finally:
        monkeypatch.undo()

    assert str((root / "sub" / "c.py").resolve()) in result.output
    assert str((root / "a.py").resolve()) in result.output
    assert str((root / "b.txt").resolve()) not in result.output
    assert asked[0] == ("glob", ["**/*.py"])


def test_glob_returns_no_files_message() -> None:
    root = (Path(".").resolve() / "virtual_project").resolve()
    monkeypatch = pytest.MonkeyPatch()
    _install_virtual_tree(monkeypatch, {})
    try:
        tool = create_glob_tool()
        instance = _run(tool.init("general"))
        asked: list[tuple[str, list[str]]] = []
        result = _run(instance.execute({"pattern": "*.md"}, _context(asked, directory=root)))
    finally:
        monkeypatch.undo()

    assert result.output == "No files found"


def test_glob_asks_external_directory_for_outside_path() -> None:
    root = (Path(".").resolve() / "virtual_project").resolve()
    outside = (root.parent / "outside").resolve()
    monkeypatch = pytest.MonkeyPatch()
    _install_virtual_tree(monkeypatch, {})
    try:
        tool = create_glob_tool()
        instance = _run(tool.init("general"))
        asked: list[tuple[str, list[str]]] = []
        _ = _run(
            instance.execute(
                {"pattern": "*.py", "path": str(outside)},
                _context(asked, directory=root),
            )
        )
    finally:
        monkeypatch.undo()

    assert ("external_directory", [str(outside)]) in asked
