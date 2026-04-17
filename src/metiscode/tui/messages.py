"""Message display widgets placeholder."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MessageList:
    """Simple in-memory message renderer model."""

    entries: list[dict[str, object]] = field(default_factory=list)

    def add_message(self, message: dict[str, object]) -> None:
        self.entries.append(message)

    def update_part(self, part: dict[str, object]) -> None:
        self.entries.append({"type": "part_update", "part": part})


def render_user_message(content: str) -> str:
    return f"User: {content}"


def render_assistant_tool_part(tool_name: str, state: str) -> str:
    return f"Tool {tool_name} [{state}]"

