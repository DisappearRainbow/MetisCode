import asyncio
import tempfile
from collections.abc import Awaitable
from pathlib import Path
from typing import TypeVar

from metiscode.project.service import GLOBAL_PROJECT_ID, ProjectService, contains_path

T = TypeVar("T")

def _run(coro: Awaitable[T]) -> T:  # noqa: UP047
    return asyncio.run(coro)


def test_from_directory_in_git_repo() -> None:
    service = ProjectService()
    result = _run(service.from_directory("."))
    assert result.project.vcs == "git"
    assert result.project.id != ""


def test_from_directory_non_git_uses_global() -> None:
    base_dir = Path.home() / ".codex" / "memories"
    base_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="metiscode-non-git-", dir=base_dir))

    service = ProjectService()
    result = _run(service.from_directory(str(temp_dir)))

    assert result.project.id == GLOBAL_PROJECT_ID
    assert result.project.worktree == "/"
    assert result.sandbox == "/"


def test_contains_path_respects_directory_and_worktree() -> None:
    current = Path(".").resolve()
    inside = current / "src" / "metiscode" / "__init__.py"
    outside = current.parent / "outside.txt"

    assert contains_path(directory=str(current), worktree="/", filepath=str(inside))
    assert not contains_path(directory=str(current), worktree="/", filepath=str(outside))
