"""Textual application scaffold."""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Footer, Header

from metiscode.tui.client import EventFrame, ServerClient
from metiscode.tui.dialogs import ModelSwitcherDialog, SessionPickerDialog
from metiscode.tui.keybindings import load_keybindings
from metiscode.tui.messages import MessageList
from metiscode.tui.prompt import PromptInput, PromptSubmitted, parse_slash_command
from metiscode.tui.themes import Theme, load_theme


class ServerEvent(Message):
    def __init__(self, frame: EventFrame) -> None:
        self.frame = frame
        super().__init__()


class MetiscodeApp(App[None]):
    """Metiscode Textual application shell."""

    CSS_PATH = "app.tcss"
    theme_name = reactive("dark")
    _DEFAULT_MODELS = [
        "anthropic:claude-sonnet-4-20250514",
        "openai:gpt-4.1",
        "openai:o4-mini",
        "deepseek:deepseek-chat",
    ]
    _DEFAULT_AGENT = "build"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:4096",
        model: str = "anthropic:claude-sonnet-4-20250514",
        session_id: str | None = None,
        client: ServerClient | None = None,
    ) -> None:
        super().__init__()
        self.base_url = base_url
        self.model = model
        self.session_id = session_id
        self._client = client or ServerClient(base_url)
        self._event_task: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield MessageList(id="messages")
        yield Container(PromptInput(id="prompt_input"), id="prompt")
        yield Footer()

    def on_mount(self) -> None:
        for binding in load_keybindings(None):
            self.bind(binding.key, binding.action, description=binding.description)
        self._event_task = asyncio.create_task(self._consume_events())

    async def on_unmount(self) -> None:
        if self._event_task is not None:
            self._event_task.cancel()
            await asyncio.gather(self._event_task, return_exceptions=True)
        await self._client.close()

    def watch_theme_name(self, _old: str, _new: str) -> None:
        self.load_theme()

    def load_theme(self) -> Theme:
        return load_theme(self.theme_name)

    def action_new_session(self) -> None:
        self.session_id = None

    def action_clear(self) -> None:
        return None

    def action_palette(self) -> None:
        return None

    async def action_session_picker(self) -> None:
        sessions = [item.model_dump() for item in await self._client.list_sessions()]

        def _on_selected(selected: str | None) -> None:
            if isinstance(selected, str) and selected:
                self.session_id = selected

        await self.push_screen(SessionPickerDialog(sessions), callback=_on_selected)

    async def action_model_switcher(self) -> None:
        def _on_selected(selected: str | None) -> None:
            if isinstance(selected, str) and selected:
                self.model = selected

        await self.push_screen(ModelSwitcherDialog(self._DEFAULT_MODELS), callback=_on_selected)

    async def on_prompt_submitted(self, event: PromptSubmitted) -> None:
        content = event.content.strip()
        if not content:
            return

        slash = parse_slash_command(content)
        if slash is not None:
            command, argument = slash
            if command == "model" and argument.strip():
                self.model = argument.strip()
            elif command == "session":
                self.session_id = argument.strip() or None
            return

        message_list = self.query_one(MessageList)
        message_list.add_message(
            {
                "role": "user",
                "parts": [{"type": "text", "content": content}],
            }
        )

        if self.session_id is None:
            created = await self._client.create_session(self.model, self._DEFAULT_AGENT)
            self.session_id = created.id

        await self._client.post_message(
            self.session_id,
            content,
            self.model,
            self._DEFAULT_AGENT,
        )

    async def _consume_events(self) -> None:
        try:
            async for frame in self._client.stream_events(session_id=self.session_id):
                self.post_message(ServerEvent(frame))
        except Exception:  # noqa: BLE001
            return

    def on_server_event(self, event: ServerEvent) -> None:
        if event.frame.type != "part.created":
            return
        if not isinstance(event.frame.properties, dict):
            return
        data = event.frame.properties.get("data")
        if isinstance(data, dict):
            self.query_one(MessageList).update_part(data)
