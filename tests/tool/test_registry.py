import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from pydantic import BaseModel, ConfigDict

from metiscode.tool import ToolContext, ToolRegistry, ToolResult, define

T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:  # noqa: UP047
    return asyncio.run(coro)


class EmptyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _dummy_ctx() -> ToolContext:
    async def ask(_permission: str, _patterns: list[str]) -> None:
        return None

    def metadata(_payload: dict[str, object]) -> None:
        return None

    return ToolContext(
        session_id="sess_1",
        message_id="msg_1",
        agent="general",
        abort=asyncio.Event(),
        metadata=metadata,
        ask=ask,
    )


def _make_tool(tool_id: str) -> object:
    async def execute(_params: EmptyParams, _ctx: ToolContext) -> ToolResult:
        return ToolResult(title=tool_id, output=tool_id, metadata={})

    return define(tool_id, f"{tool_id} tool", EmptyParams, execute)


class _Wrap:
    def __init__(self, tool: object, allowed_agents: set[str] | None = None) -> None:
        self._tool = tool
        self.id = tool.id  # type: ignore[attr-defined]
        self.allowed_agents = allowed_agents

    async def init(self, agent: str | None = None) -> object:
        return await self._tool.init(agent)  # type: ignore[attr-defined]


def test_register_and_get_roundtrip() -> None:
    registry = ToolRegistry()
    tool = _Wrap(_make_tool("alpha"))
    registry.register(tool)  # type: ignore[arg-type]
    fetched = registry.get("alpha")
    assert fetched is not None
    assert fetched.id == "alpha"


def test_ids_returns_sorted_ids() -> None:
    registry = ToolRegistry()
    registry.register(_Wrap(_make_tool("zeta")))  # type: ignore[arg-type]
    registry.register(_Wrap(_make_tool("beta")))  # type: ignore[arg-type]
    registry.register(_Wrap(_make_tool("alpha")))  # type: ignore[arg-type]
    assert registry.ids() == ["alpha", "beta", "zeta"]


def test_get_tools_filters_subagent_only_tools() -> None:
    registry = ToolRegistry()
    general_tool = _Wrap(_make_tool("general_tool"))
    subagent_tool = _Wrap(_make_tool("subagent_tool"), allowed_agents={"general"})

    registry.register(general_tool)  # type: ignore[arg-type]
    registry.register(subagent_tool)  # type: ignore[arg-type]

    general_instances = _run(registry.get_tools(agent="general"))
    subagent_instances = _run(registry.get_tools(agent="subagent"))

    assert sorted(instance.description for instance in general_instances) == [
        "general_tool tool",
        "subagent_tool tool",
    ]
    assert [instance.description for instance in subagent_instances] == ["general_tool tool"]
    _ = _run(general_instances[0].execute({}, _dummy_ctx()))
