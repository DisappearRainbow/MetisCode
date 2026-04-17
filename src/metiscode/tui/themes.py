"""Theme definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Theme:
    name: str
    bg: str
    fg: str
    accent: str
    error: str
    warning: str
    success: str
    muted: str
    border: str


_THEMES = {
    "dark": Theme(
        name="dark",
        bg="#111318",
        fg="#F2F4F8",
        accent="#6EA8FE",
        error="#FF6B6B",
        warning="#FFD166",
        success="#06D6A0",
        muted="#AAB1C3",
        border="#2A2F3A",
    ),
    "light": Theme(
        name="light",
        bg="#FAFBFD",
        fg="#1F2937",
        accent="#2563EB",
        error="#DC2626",
        warning="#D97706",
        success="#059669",
        muted="#6B7280",
        border="#D1D5DB",
    ),
}


def load_theme(name: str) -> Theme:
    return _THEMES.get(name, _THEMES["dark"])

