import asyncio
from collections.abc import Awaitable
from pathlib import Path
from typing import TypeVar

import pytest

from metiscode.tool import ToolContext, create_read_tool

T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:  # noqa: UP047
    return asyncio.run(coro)


def _install_virtual_files(
    monkeypatch: pytest.MonkeyPatch,
    files: dict[Path, str],
) -> None:
    normalized = {str(path.resolve()): content for path, content in files.items()}

    def _fake_read_text(self: Path, encoding: str = "utf-8") -> str:
        _ = encoding
        key = str(self.resolve())
        if key not in normalized:
            raise FileNotFoundError(key)
        return normalized[key]

    monkeypatch.setattr(Path, "read_text", _fake_read_text)


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


def test_read_outputs_line_number_format(monkeypatch: pytest.MonkeyPatch) -> None:
    root = (Path(".").resolve() / "virtual_project").resolve()
    file_path = (root / "a.txt").resolve()
    _install_virtual_files(monkeypatch, {file_path: "alpha\nbeta\ngamma\n"})

    tool = create_read_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    result = _run(instance.execute({"file_path": str(file_path)}, _context(asked, directory=root)))

    assert result.output == "1\talpha\n2\tbeta\n3\tgamma"
    assert asked == []


def test_read_applies_offset_and_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    root = (Path(".").resolve() / "virtual_project").resolve()
    file_path = (root / "b.txt").resolve()
    _install_virtual_files(monkeypatch, {file_path: "one\ntwo\nthree\nfour\n"})

    tool = create_read_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    result = _run(
        instance.execute(
            {"file_path": str(file_path), "offset": 1, "limit": 2},
            _context(asked, directory=root),
        )
    )

    assert result.output == "2\ttwo\n3\tthree"
    assert asked == []


def test_asks_external_directory_for_absolute_outside_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = (Path(".").resolve() / "virtual_project").resolve()
    file_path = (root.parent / "outside.txt").resolve()
    _install_virtual_files(monkeypatch, {file_path: "x\n"})

    tool = create_read_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    _ = _run(instance.execute({"file_path": str(file_path)}, _context(asked, directory=root)))

    assert asked
    assert asked[0][0] == "external_directory"
    assert asked[0][1] == [str(file_path.parent)]


def test_asks_external_directory_for_relative_outside_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = (Path(".").resolve() / "virtual_project").resolve()
    external = (root.parent / "virtual_external").resolve()
    file_path = (external / "outside_rel.txt").resolve()
    _install_virtual_files(monkeypatch, {file_path: "z\n"})

    relative = str(file_path.relative_to(root.parent))
    candidate = f"..\\{relative}" if "\\" in relative else f"../{relative}"

    tool = create_read_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    _ = _run(instance.execute({"file_path": candidate}, _context(asked, directory=root)))

    assert asked
    assert asked[0][0] == "external_directory"


def test_does_not_ask_external_directory_for_inside_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = (Path(".").resolve() / "virtual_project").resolve()
    file_path = (root / "nested" / "inside.txt").resolve()
    _install_virtual_files(monkeypatch, {file_path: "inside\n"})

    tool = create_read_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    _ = _run(instance.execute({"file_path": "nested/inside.txt"}, _context(asked, directory=root)))

    assert asked == []
