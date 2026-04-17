"""MCP client stub."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class McpServerConfig:
    name: str
    transport: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None


@dataclass(slots=True, frozen=True)
class McpConfig:
    servers: list[McpServerConfig]


@dataclass(slots=True)
class McpClient:
    config: McpConfig
    connect_adapter: Callable[[McpServerConfig], Awaitable[None]] | None = None
    discover_adapter: Callable[[McpServerConfig], Awaitable[list[dict[str, object]]]] | None = None
    execute_adapter: Callable[[str, str, dict[str, object]], Awaitable[str]] | None = None
    _connected: bool = False

    @classmethod
    def from_config(cls, mcp_config: McpConfig) -> McpClient:
        return cls(config=mcp_config)

    async def connect(self) -> None:
        for server in self.config.servers:
            if self.connect_adapter is not None:
                await self.connect_adapter(server)
        self._connected = True

    async def discover_tools(self) -> list[dict[str, object]]:
        tools: list[dict[str, object]] = []
        for server in self.config.servers:
            if self.discover_adapter is None:
                continue
            discovered = await self.discover_adapter(server)
            tools.extend(discovered)
        return tools

    async def execute_tool(
        self,
        server_name: str,
        tool_name: str,
        params: dict[str, object],
    ) -> str:
        if self.execute_adapter is None:
            raise RuntimeError("No execute adapter configured")
        return await self.execute_adapter(server_name, tool_name, params)

    async def disconnect(self) -> None:
        self._connected = False
