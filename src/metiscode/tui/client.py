"""HTTP and websocket client for TUI."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

import httpx
import websockets
from pydantic import BaseModel, ConfigDict


class SessionInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str | None = None
    model: str | None = None
    agent: str | None = None


class MessageInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    message_id: str | None = None
    session_id: str
    role: str | None = None
    content: str | None = None
    data: dict[str, Any] | None = None


class EventFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    properties: dict[str, Any] | None = None


class WSClient:
    def __init__(self, websocket: Any) -> None:
        self._websocket = websocket

    async def send_json(self, payload: dict[str, object]) -> None:
        await self._websocket.send(json.dumps(payload, ensure_ascii=False))

    async def recv_json(self) -> dict[str, object]:
        raw = await self._websocket.recv()
        if not isinstance(raw, str):
            raise RuntimeError("websocket payload must be text")
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        raise RuntimeError("websocket payload must be JSON object")


class ServerClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(base_url=self.base_url)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def list_sessions(self) -> list[SessionInfo]:
        response = await self._client.get("/session")
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            return []
        return [SessionInfo.model_validate(item) for item in data if isinstance(item, dict)]

    async def create_session(self, model: str | None, agent: str | None) -> SessionInfo:
        response = await self._client.post("/session", json={"model": model, "agent": agent})
        response.raise_for_status()
        return SessionInfo.model_validate(response.json())

    async def post_message(
        self,
        session_id: str,
        content: str,
        model: str,
        agent: str,
    ) -> MessageInfo:
        response = await self._client.post(
            f"/session/{session_id}/message",
            json={"content": content, "model": model, "agent": agent},
        )
        response.raise_for_status()
        return MessageInfo.model_validate(response.json())

    async def get_messages(self, session_id: str) -> list[MessageInfo]:
        response = await self._client.get(f"/session/{session_id}/message")
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            return []
        return [MessageInfo.model_validate(item) for item in data if isinstance(item, dict)]

    async def stream_events(self, session_id: str | None = None) -> AsyncIterator[EventFrame]:
        params: dict[str, str] = {}
        if session_id is not None:
            params["session_id"] = session_id
        async with self._client.stream("GET", "/event", params=params, timeout=None) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload:
                    continue
                data = json.loads(payload)
                if isinstance(data, dict):
                    yield EventFrame.model_validate(data)

    @asynccontextmanager
    async def connect_ws(self) -> AsyncIterator[WSClient]:
        parsed = urlparse(self.base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        ws_url = f"{scheme}://{parsed.netloc}/ws"
        async with websockets.connect(ws_url) as websocket:
            yield WSClient(websocket)
