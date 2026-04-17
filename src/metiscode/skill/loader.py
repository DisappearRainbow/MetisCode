"""JSON skill loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class SkillInfo:
    name: str
    description: str
    system_prompt: str
    tools: list[str]


class SkillLoader:
    """Load skills from project and user skill directories."""

    def __init__(self, *, project_dir: Path | None = None, home_dir: Path | None = None) -> None:
        self.project_dir = project_dir or Path(".").resolve()
        self.home_dir = home_dir or Path.home()
        self._cache: dict[str, SkillInfo] | None = None

    def _search_paths(self) -> list[Path]:
        return [
            self.project_dir / ".metiscode" / "skills",
            self.home_dir / ".metiscode" / "skills",
        ]

    def load_all(self) -> dict[str, SkillInfo]:
        result: dict[str, SkillInfo] = {}
        for directory in self._search_paths():
            if not directory.exists():
                continue
            for file_path in directory.glob("*.json"):
                try:
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(data, dict):
                    continue
                name = data.get("name")
                description = data.get("description")
                system_prompt = data.get("system_prompt")
                tools = data.get("tools")
                if not isinstance(name, str):
                    continue
                if not isinstance(description, str):
                    description = ""
                if not isinstance(system_prompt, str):
                    system_prompt = ""
                if not isinstance(tools, list):
                    tools = []
                tool_names = [str(item) for item in tools]
                result[name] = SkillInfo(
                    name=name,
                    description=description,
                    system_prompt=system_prompt,
                    tools=tool_names,
                )
        self._cache = result
        return result

    def get(self, name: str) -> SkillInfo | None:
        if self._cache is None:
            self.load_all()
        assert self._cache is not None
        return self._cache.get(name)

