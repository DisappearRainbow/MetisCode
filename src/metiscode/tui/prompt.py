"""Prompt input widget placeholder."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class PromptSubmitted:
    content: str
    files: list[str]


@dataclass(slots=True)
class PromptInput:
    """In-memory prompt input model with history and slash commands."""

    history_limit: int = 100
    history: list[str] = field(default_factory=list)
    _history_index: int | None = None

    def submit(self, content: str, files: list[str] | None = None) -> PromptSubmitted:
        self._append_history(content)
        return PromptSubmitted(content=content, files=files or [])

    def _append_history(self, content: str) -> None:
        text = content.strip()
        if not text:
            return
        self.history.append(text)
        if len(self.history) > self.history_limit:
            self.history = self.history[-self.history_limit :]
        self._history_index = None

    def history_up(self) -> str | None:
        if not self.history:
            return None
        if self._history_index is None:
            self._history_index = len(self.history) - 1
        else:
            self._history_index = max(0, self._history_index - 1)
        return self.history[self._history_index]

    def history_down(self) -> str | None:
        if self._history_index is None:
            return None
        self._history_index = min(len(self.history) - 1, self._history_index + 1)
        return self.history[self._history_index]

    def parse_slash_command(self, content: str) -> tuple[str, str] | None:
        if not content.startswith("/"):
            return None
        parts = content[1:].split(maxsplit=1)
        command = parts[0]
        argument = parts[1] if len(parts) > 1 else ""
        return command, argument

