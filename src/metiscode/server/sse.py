"""SSE helpers."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator


def format_sse(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def stream_events(
    source: AsyncIterator[dict[str, object]],
    *,
    session_id: str | None = None,
) -> AsyncIterator[str]:
    async for item in source:
        if session_id is not None and str(item.get("session_id")) != session_id:
            continue
        yield format_sse(item)

