import asyncio

from metiscode.mcp import McpClient, McpConfig, McpServerConfig


def test_discover_tools_returns_mocked_stdio_tools() -> None:
    async def discover(server: McpServerConfig):  # type: ignore[no-untyped-def]
        return [{"server": server.name, "name": "tool_a"}]

    client = McpClient.from_config(
        McpConfig(servers=[McpServerConfig(name="stdio1", transport="stdio", command="python")])
    )
    client.discover_adapter = discover
    tools = asyncio.run(client.discover_tools())
    assert tools == [{"server": "stdio1", "name": "tool_a"}]


def test_execute_tool_forwards_params_and_returns_result() -> None:
    received: list[tuple[str, str, dict[str, object]]] = []

    async def execute(server_name: str, tool_name: str, params: dict[str, object]) -> str:
        received.append((server_name, tool_name, params))
        return "ok"

    client = McpClient.from_config(
        McpConfig(servers=[McpServerConfig(name="stdio1", transport="stdio", command="python")])
    )
    client.execute_adapter = execute
    result = asyncio.run(client.execute_tool("stdio1", "tool_x", {"x": 1}))
    assert result == "ok"
    assert received == [("stdio1", "tool_x", {"x": 1})]

