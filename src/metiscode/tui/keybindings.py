"""Keybinding models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Keybinding:
    key: str
    action: str
    description: str


def load_keybindings(config: dict[str, object] | None) -> list[Keybinding]:
    _ = config
    return [
        Keybinding("ctrl+c", "quit", "Quit app"),
        Keybinding("ctrl+n", "new_session", "Create new session"),
        Keybinding("ctrl+l", "clear", "Clear screen"),
        Keybinding("ctrl+k", "palette", "Command palette"),
    ]

