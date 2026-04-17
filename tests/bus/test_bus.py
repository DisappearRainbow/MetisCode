import asyncio

from pydantic import BaseModel, ConfigDict

from metiscode.bus import BusEvent, EventBus, EventEnvelope


class AEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str


class BEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int


async def _wait_until(predicate, timeout: float = 1.0) -> None:  # type: ignore[no-untyped-def]
    async def _inner() -> None:
        while not predicate():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(_inner(), timeout=timeout)


def test_publish_delivers_to_typed_subscriber() -> None:
    async def scenario() -> None:
        bus = EventBus()
        definition = BusEvent.define("event.a", AEvent)
        received: list[AEvent] = []

        async def callback(event: AEvent) -> None:
            received.append(event)

        unsubscribe = await bus.subscribe(definition, callback)
        await bus.publish(definition, AEvent(value="hello"))
        await _wait_until(lambda: len(received) == 1)
        assert received[0].value == "hello"

        await unsubscribe()
        await bus.close()

    asyncio.run(scenario())


def test_subscribe_all_receives_all_event_types() -> None:
    async def scenario() -> None:
        bus = EventBus()
        event_a = BusEvent.define("event.a2", AEvent)
        event_b = BusEvent.define("event.b2", BEvent)
        received: list[EventEnvelope] = []

        async def callback(event: EventEnvelope) -> None:
            received.append(event)

        unsubscribe = await bus.subscribe_all(callback)
        await bus.publish(event_a, AEvent(value="alpha"))
        await bus.publish(event_b, BEvent(count=2))
        await _wait_until(lambda: len(received) == 2)

        assert [item.type_name for item in received] == ["event.a2", "event.b2"]
        await unsubscribe()
        await bus.close()

    asyncio.run(scenario())


def test_unsubscribe_stops_future_delivery() -> None:
    async def scenario() -> None:
        bus = EventBus()
        definition = BusEvent.define("event.a3", AEvent)
        received: list[str] = []

        async def callback(event: AEvent) -> None:
            received.append(event.value)

        unsubscribe = await bus.subscribe(definition, callback)
        await bus.publish(definition, AEvent(value="one"))
        await _wait_until(lambda: len(received) == 1)

        await unsubscribe()
        await bus.publish(definition, AEvent(value="two"))
        await asyncio.sleep(0.05)
        assert received == ["one"]

        await bus.close()

    asyncio.run(scenario())


def test_multiple_subscribers_receive_independent_copies() -> None:
    async def scenario() -> None:
        bus = EventBus()
        definition = BusEvent.define("event.a4", AEvent)
        first: list[str] = []
        second: list[str] = []

        async def callback_first(event: AEvent) -> None:
            first.append(event.value)

        async def callback_second(event: AEvent) -> None:
            second.append(event.value)

        unsubscribe_first = await bus.subscribe(definition, callback_first)
        unsubscribe_second = await bus.subscribe(definition, callback_second)
        await bus.publish(definition, AEvent(value="shared"))
        await _wait_until(lambda: len(first) == 1 and len(second) == 1)

        assert first == ["shared"]
        assert second == ["shared"]

        await unsubscribe_first()
        await unsubscribe_second()
        await bus.close()

    asyncio.run(scenario())

