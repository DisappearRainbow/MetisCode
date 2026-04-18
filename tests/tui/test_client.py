import json

import httpx
import pytest

from metiscode.tui.client import ServerClient


@pytest.mark.anyio
async def test_list_sessions_calls_get_session() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/session"
        return httpx.Response(200, json=[{"id": "s1", "title": "t1"}])

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    )
    client = ServerClient("http://test", client=http_client)
    sessions = await client.list_sessions()
    await http_client.aclose()

    assert sessions and sessions[0].id == "s1"


@pytest.mark.anyio
async def test_list_sessions_ignores_extra_fields() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/session"
        return httpx.Response(
            200,
            json=[
                {
                    "id": "s1",
                    "title": "t1",
                    "project_id": "global",
                    "time_created": 1,
                }
            ],
        )

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    )
    client = ServerClient("http://test", client=http_client)
    sessions = await client.list_sessions()
    await http_client.aclose()

    assert sessions and sessions[0].id == "s1"


@pytest.mark.anyio
async def test_create_session_posts_body() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/session"
        assert json.loads(request.content.decode("utf-8")) == {
            "model": "openai:gpt-4.1",
            "agent": "build",
        }
        return httpx.Response(201, json={"id": "s1", "model": "openai:gpt-4.1", "agent": "build"})

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    )
    client = ServerClient("http://test", client=http_client)
    created = await client.create_session("openai:gpt-4.1", "build")
    await http_client.aclose()

    assert created.id == "s1"


@pytest.mark.anyio
async def test_post_message_calls_correct_endpoint() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/session/s1/message"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["content"] == "hello"
        return httpx.Response(202, json={"message_id": "m1", "session_id": "s1"})

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    )
    client = ServerClient("http://test", client=http_client)
    posted = await client.post_message("s1", "hello", "openai:gpt-4.1", "build")
    await http_client.aclose()

    assert posted.message_id == "m1"
    assert posted.session_id == "s1"


@pytest.mark.anyio
async def test_stream_events_parses_sse_frames() -> None:
    payload = "\n".join(
        [
            'data: {"type":"server.connected"}',
            "",
            'data: {"type":"part.created","properties":{"session_id":"s1"}}',
            "",
        ]
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/event"
        return httpx.Response(200, text=payload)

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    )
    client = ServerClient("http://test", client=http_client)
    frames = [frame async for frame in client.stream_events("s1")]
    await http_client.aclose()

    assert [frame.type for frame in frames] == ["server.connected", "part.created"]
    assert frames[1].properties == {"session_id": "s1"}


@pytest.mark.anyio
async def test_connect_ws_uses_ws_endpoint(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    called: list[str] = []
    sent: list[str] = []

    class _FakeWS:
        async def send(self, payload: str) -> None:
            sent.append(payload)

        async def recv(self) -> str:
            return '{"type":"ack"}'

    class _FakeConnect:
        def __init__(self, ws_url: str) -> None:
            called.append(ws_url)
            self._ws = _FakeWS()

        async def __aenter__(self) -> _FakeWS:
            return self._ws

        async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
            _ = (exc_type, exc, tb)
            return None

    def fake_connect(ws_url: str) -> _FakeConnect:
        return _FakeConnect(ws_url)

    monkeypatch.setattr("metiscode.tui.client.websockets.connect", fake_connect)
    client = ServerClient("http://127.0.0.1:4096")
    async with client.connect_ws() as ws:
        await ws.send_json({"type": "ping"})
        received = await ws.recv_json()
    await client.close()

    assert called == ["ws://127.0.0.1:4096/ws"]
    assert sent and '"type": "ping"' in sent[0]
    assert received["type"] == "ack"
