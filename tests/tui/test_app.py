import asyncio

import pytest
from textual.widgets import Footer, Header, Markdown

from metiscode.tui import EventFrame, MessageList, MetiscodeApp, SessionInfo
from metiscode.tui.prompt import PromptSubmitted


class _NoopClient:
    def __init__(self) -> None:
        self.closed = False

    async def stream_events(self, session_id: str | None = None):  # type: ignore[no-untyped-def]
        _ = session_id
        if False:
            yield EventFrame(type="noop")

    async def close(self) -> None:
        self.closed = True

    async def list_sessions(self) -> list[SessionInfo]:
        return []


@pytest.mark.anyio
async def test_app_runs_under_textual_pilot() -> None:
    app = MetiscodeApp(client=_NoopClient())
    async with app.run_test():
        assert app.is_mounted


@pytest.mark.anyio
async def test_app_has_header_and_footer_widgets() -> None:
    app = MetiscodeApp(client=_NoopClient())
    async with app.run_test() as pilot:
        assert pilot.app.query_one(Header) is not None
        assert pilot.app.query_one(Footer) is not None


@pytest.mark.anyio
async def test_app_consumes_part_created_events_into_message_list() -> None:
    class _EventClient:
        def __init__(self) -> None:
            self.closed = False

        async def stream_events(self, session_id: str | None = None):  # type: ignore[no-untyped-def]
            _ = session_id
            yield EventFrame(
                type="part.created",
                properties={"data": {"type": "text", "content": "one"}},
            )
            yield EventFrame(
                type="part.created",
                properties={"data": {"type": "text", "content": "two"}},
            )

        async def close(self) -> None:
            self.closed = True

    app = MetiscodeApp(client=_EventClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        message_list = pilot.app.query_one(MessageList)
        markdowns = list(message_list.query(Markdown))
        assert len(markdowns) >= 2


@pytest.mark.anyio
async def test_app_unmount_cancels_event_task() -> None:
    class _SlowClient:
        def __init__(self) -> None:
            self.closed = False

        async def stream_events(self, session_id: str | None = None):  # type: ignore[no-untyped-def]
            _ = session_id
            while True:
                await asyncio.sleep(1)
                yield EventFrame(
                    type="part.created",
                    properties={"data": {"type": "text", "content": "tick"}},
                )

        async def close(self) -> None:
            self.closed = True

    client = _SlowClient()
    app = MetiscodeApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app._event_task is not None  # type: ignore[attr-defined]
    assert app._event_task is not None  # type: ignore[attr-defined]
    assert app._event_task.cancelled() is True  # type: ignore[attr-defined]
    assert client.closed is True


@pytest.mark.anyio
async def test_action_session_picker_updates_session_id(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class _Client(_NoopClient):
        async def list_sessions(self) -> list[SessionInfo]:
            return [SessionInfo(id="s1", title="Session 1")]

    app = MetiscodeApp(client=_Client())
    async with app.run_test() as pilot:
        async def fake_push_screen(_screen, callback=None):  # type: ignore[no-untyped-def]
            if callback is not None:
                callback("s1")
            return None

        monkeypatch.setattr(pilot.app, "push_screen", fake_push_screen)
        await pilot.app.action_session_picker()
        assert pilot.app.session_id == "s1"


@pytest.mark.anyio
async def test_action_model_switcher_updates_model(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    app = MetiscodeApp(client=_NoopClient())
    async with app.run_test() as pilot:
        async def fake_push_screen(_screen, callback=None):  # type: ignore[no-untyped-def]
            if callback is not None:
                callback("openai:gpt-4.1")
            return None

        monkeypatch.setattr(pilot.app, "push_screen", fake_push_screen)
        await pilot.app.action_model_switcher()
        assert pilot.app.model == "openai:gpt-4.1"


@pytest.mark.anyio
async def test_prompt_submit_creates_session_and_posts_message() -> None:
    class _Client(_NoopClient):
        def __init__(self) -> None:
            super().__init__()
            self.created: list[tuple[str | None, str | None]] = []
            self.posted: list[tuple[str, str, str, str]] = []

        async def create_session(self, model: str | None, agent: str | None) -> SessionInfo:
            self.created.append((model, agent))
            return SessionInfo(id="s-created", model=model, agent=agent)

        async def post_message(
            self,
            session_id: str,
            content: str,
            model: str,
            agent: str,
        ):  # type: ignore[no-untyped-def]
            self.posted.append((session_id, content, model, agent))
            return {"message_id": "m1", "session_id": session_id}

    client = _Client()
    app = MetiscodeApp(client=client)
    async with app.run_test() as pilot:
        await pilot.app.on_prompt_submitted(PromptSubmitted("say hi"))
        await pilot.pause()

    assert client.created == [("anthropic:claude-sonnet-4-20250514", "build")]
    assert client.posted == [("s-created", "say hi", "anthropic:claude-sonnet-4-20250514", "build")]
