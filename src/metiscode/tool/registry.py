"""Tool registry service."""

from __future__ import annotations

from typing import Any

from metiscode.tool.tool import ToolInfo, ToolInstance


class ToolRegistry:
    """Registry for tool definitions."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolInfo[Any]] = {}

    def register(self, tool: ToolInfo[Any]) -> None:
        """Register or replace a tool by id."""
        self._tools[tool.id] = tool

    def ids(self) -> list[str]:
        """Return all tool ids in sorted order."""
        return sorted(self._tools.keys())

    def get(self, tool_id: str) -> ToolInfo[Any] | None:
        """Get tool by id."""
        return self._tools.get(tool_id)

    async def get_tools(self, agent: str, model: str | None = None) -> list[ToolInstance[Any]]:
        """Get initialized tools filtered by agent and optional model hints."""
        _ = model
        result: list[ToolInstance[Any]] = []
        for tool in self._tools.values():
            allowed_agents = getattr(tool, "allowed_agents", None)
            if isinstance(allowed_agents, (set, list, tuple)):
                if agent not in allowed_agents and "*" not in allowed_agents:
                    continue
            instance = await tool.init(agent)
            result.append(instance)
        return result

