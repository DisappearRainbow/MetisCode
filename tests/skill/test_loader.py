import asyncio
import json
import shutil
from collections.abc import Awaitable
from pathlib import Path
from typing import TypeVar

from metiscode.skill import SkillLoader
from metiscode.tool import ToolContext, create_skill_tool

T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:  # noqa: UP047
    return asyncio.run(coro)


def _make_dirs(base: Path) -> tuple[Path, Path]:
    project_dir = base / "project"
    home_dir = base / "home"
    (project_dir / ".metiscode" / "skills").mkdir(parents=True, exist_ok=True)
    (home_dir / ".metiscode" / "skills").mkdir(parents=True, exist_ok=True)
    return project_dir, home_dir


def test_loader_loads_valid_skill_json() -> None:
    base = Path(".").resolve() / ".metiscode" / "tmp" / "skill_loader_1"
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    project_dir, home_dir = _make_dirs(base)
    file_path = project_dir / ".metiscode" / "skills" / "commit.json"
    file_path.write_text(
        json.dumps(
            {
                "name": "commit",
                "description": "Create commit",
                "system_prompt": "You are commit assistant",
                "tools": ["bash", "read"],
            }
        ),
        encoding="utf-8",
    )
    loader = SkillLoader(project_dir=project_dir, home_dir=home_dir)
    skills = loader.load_all()
    assert "commit" in skills
    assert skills["commit"].tools == ["bash", "read"]


def test_loader_returns_empty_when_no_skill_files() -> None:
    base = Path(".").resolve() / ".metiscode" / "tmp" / "skill_loader_2"
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    project_dir, home_dir = _make_dirs(base)
    loader = SkillLoader(project_dir=project_dir, home_dir=home_dir)
    skills = loader.load_all()
    assert skills == {}


def test_skill_tool_loads_skill_from_loader() -> None:
    base = Path(".").resolve() / ".metiscode" / "tmp" / "skill_loader_3"
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    project_dir, home_dir = _make_dirs(base)
    file_path = project_dir / ".metiscode" / "skills" / "writer.json"
    file_path.write_text(
        json.dumps(
            {
                "name": "writer",
                "description": "Write files",
                "system_prompt": "Use write and edit tools",
                "tools": ["write", "edit"],
            }
        ),
        encoding="utf-8",
    )

    asked: list[tuple[str, list[str]]] = []

    async def ask(permission: str, patterns: list[str]) -> None:
        asked.append((permission, patterns))

    def metadata(_payload: dict[str, object]) -> None:
        return None

    tool = create_skill_tool()
    instance = _run(tool.init("general"))
    original_cwd = Path.cwd()
    try:
        import os

        os.chdir(project_dir)
        result = _run(
            instance.execute(
                {"skill_name": "writer"},
                ToolContext(
                    session_id="s1",
                    message_id="m1",
                    agent="general",
                    abort=asyncio.Event(),
                    metadata=metadata,
                    ask=ask,
                ),
            )
        )
    finally:
        os.chdir(original_cwd)

    assert "write and edit tools" in result.output
    assert asked[0] == ("skill", ["writer"])

