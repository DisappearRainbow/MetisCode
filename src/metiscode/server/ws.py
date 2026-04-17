"""WebSocket command bridge abstractions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable


class WsBridge:
    """Handle inbound websocket command payloads."""

    def __init__(
        self,
        *,
        on_permission_reply: Callable[[str, str], Awaitable[None]],
        on_abort: Callable[[str], Awaitable[None]],
    ) -> None:
        self._on_permission_reply = on_permission_reply
        self._on_abort = on_abort

    async def handle_message(self, message: dict[str, object]) -> None:
        message_type = message.get("type")
        if message_type == "permission_reply":
            request_id = str(message.get("request_id", ""))
            action = str(message.get("action", ""))
            await self._on_permission_reply(request_id, action)
            return
        if message_type == "abort":
            session_id = str(message.get("session_id", ""))
            await self._on_abort(session_id)

