"""In-process async event bus."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from metiscode.bus.event import EventDefinition


@dataclass(slots=True, frozen=True)
class EventEnvelope:
    """Published event payload with type tag."""

    type_name: str
    properties: BaseModel


@dataclass(slots=True)
class _Subscriber:
    queue: asyncio.Queue[object]
    task: asyncio.Task[None]


class EventBus:
    """Async pub/sub bus with per-subscriber queue backpressure."""

    def __init__(self, queue_size: int = 256) -> None:
        self._queue_size = queue_size
        self._typed: dict[str, list[_Subscriber]] = {}
        self._wildcard: list[_Subscriber] = []
        self._lock = asyncio.Lock()

    async def publish(self, event_def: EventDefinition, payload: BaseModel) -> None:
        """Publish an event to typed subscribers and wildcard subscribers."""
        validated = event_def.schema.model_validate(payload.model_dump())
        envelope = EventEnvelope(type_name=event_def.type_name, properties=validated)

        async with self._lock:
            typed = list(self._typed.get(event_def.type_name, []))
            wildcard = list(self._wildcard)

        for subscriber in typed:
            await subscriber.queue.put(validated)
        for subscriber in wildcard:
            await subscriber.queue.put(envelope)

    async def subscribe(
        self,
        event_def: EventDefinition,
        callback: Any,
    ) -> Any:
        """Subscribe to one event type and return an async unsubscribe function."""
        queue: asyncio.Queue[object] = asyncio.Queue(maxsize=self._queue_size)
        task = asyncio.create_task(self._run_callback_loop(queue, callback))
        subscriber = _Subscriber(queue=queue, task=task)

        async with self._lock:
            self._typed.setdefault(event_def.type_name, []).append(subscriber)

        async def unsubscribe() -> None:
            async with self._lock:
                if event_def.type_name in self._typed:
                    self._typed[event_def.type_name] = [
                        item for item in self._typed[event_def.type_name] if item is not subscriber
                    ]
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        return unsubscribe

    async def subscribe_all(self, callback: Any) -> Any:
        """Subscribe to all event types and return an async unsubscribe function."""
        queue: asyncio.Queue[object] = asyncio.Queue(maxsize=self._queue_size)
        task = asyncio.create_task(self._run_callback_loop(queue, callback))
        subscriber = _Subscriber(queue=queue, task=task)

        async with self._lock:
            self._wildcard.append(subscriber)

        async def unsubscribe() -> None:
            async with self._lock:
                self._wildcard = [item for item in self._wildcard if item is not subscriber]
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        return unsubscribe

    async def close(self) -> None:
        """Cancel all subscriber tasks."""
        async with self._lock:
            typed = [subscriber for items in self._typed.values() for subscriber in items]
            wildcard = list(self._wildcard)
            self._typed.clear()
            self._wildcard.clear()
        for subscriber in [*typed, *wildcard]:
            subscriber.task.cancel()
        tasks = [subscriber.task for subscriber in [*typed, *wildcard]]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_callback_loop(self, queue: asyncio.Queue[object], callback: Any) -> None:
        while True:
            item = await queue.get()
            result = callback(item)
            if inspect.isawaitable(result):
                await result
