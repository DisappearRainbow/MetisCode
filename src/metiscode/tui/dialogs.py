"""TUI dialog placeholders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PermissionAction = Literal["once", "always", "deny"]


@dataclass(slots=True)
class PermissionDialog:
    request_id: str
    tool_name: str
    pattern: str

    def display_text(self) -> str:
        return f"{self.tool_name}: {self.pattern}"

    def resolve(self, action: PermissionAction) -> tuple[str, PermissionAction]:
        return self.request_id, action


@dataclass(slots=True)
class SessionPickerDialog:
    sessions: list[dict[str, object]]

    def pick(self, session_id: str) -> str | None:
        for item in self.sessions:
            if str(item.get("id")) == session_id:
                return session_id
        return None


@dataclass(slots=True)
class ModelSwitcherDialog:
    models: list[str]

    def pick(self, model: str) -> str | None:
        return model if model in self.models else None

