import asyncio

from metiscode.server.sse import stream_events
from metiscode.server.ws import WsBridge


def test_sse_stream_emits_published_event() -> None:
    async def source():  # type: ignore[no-untyped-def]
        yield {"session_id": "s1", "type": "part.created", "value": 1}

    async def collect():  # type: ignore[no-untyped-def]
        output = []
        async for item in stream_events(source(), session_id="s1"):
            output.append(item)
        return output

    events = asyncio.run(collect())
    assert events and events[0].startswith("data: ")


def test_ws_bridge_receives_bus_like_events() -> None:
    received: list[tuple[str, str]] = []

    async def on_permission_reply(request_id: str, action: str) -> None:
        received.append((request_id, action))

    async def on_abort(_session_id: str) -> None:
        return None

    bridge = WsBridge(on_permission_reply=on_permission_reply, on_abort=on_abort)
    asyncio.run(
        bridge.handle_message(
            {"type": "permission_reply", "request_id": "req1", "action": "allow"}
        )
    )
    assert received == [("req1", "allow")]


def test_ws_bridge_routes_permission_reply_and_abort() -> None:
    replies: list[tuple[str, str]] = []
    aborted: list[str] = []

    async def on_permission_reply(request_id: str, action: str) -> None:
        replies.append((request_id, action))

    async def on_abort(session_id: str) -> None:
        aborted.append(session_id)

    bridge = WsBridge(on_permission_reply=on_permission_reply, on_abort=on_abort)
    asyncio.run(bridge.handle_message({"type": "abort", "session_id": "s1"}))
    asyncio.run(
        bridge.handle_message(
            {"type": "permission_reply", "request_id": "req2", "action": "deny"}
        )
    )
    assert aborted == ["s1"]
    assert replies == [("req2", "deny")]

