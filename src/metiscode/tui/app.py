"""TUI app scaffold (dependency-light placeholder)."""

from __future__ import annotations

from dataclasses import dataclass, field

from metiscode.tui.keybindings import Keybinding, load_keybindings
from metiscode.tui.messages import MessageList
from metiscode.tui.prompt import PromptInput
from metiscode.tui.themes import Theme, load_theme


@dataclass(slots=True)
class MetiscodeApp:
    """Lightweight app scaffold compatible with current environment."""

    theme_name: str = "dark"
    model: str = "anthropic:claude-sonnet-4-20250514"
    session_id: str | None = None
    message_list: MessageList = field(default_factory=MessageList)
    prompt_input: PromptInput = field(default_factory=PromptInput)
    keybindings: list[Keybinding] = field(default_factory=list)

    def compose(self) -> dict[str, object]:
        return {
            "header": {"title": "metiscode", "model": self.model, "session_id": self.session_id},
            "body": self.message_list,
            "footer": self.prompt_input,
        }

    def on_mount(self) -> None:
        self.keybindings = load_keybindings(None)

    def load_theme(self) -> Theme:
        return load_theme(self.theme_name)

