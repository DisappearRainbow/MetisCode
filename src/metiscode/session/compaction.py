"""Context compaction utilities."""

from __future__ import annotations

from typing import Protocol

from metiscode.provider import ModelInfo
from metiscode.util.ids import ulid_str

PRUNE_MINIMUM = 20_000
PRUNE_PROTECT = 40_000


class CompactionDBProtocol(Protocol):
    async def get_messages(self, session_id: str) -> list[dict[str, object]]: ...
    async def get_message_parts(self, message_id: str) -> list[dict[str, object]]: ...
    async def update_part(self, part_id: str, *, data: dict[str, object] | None = None) -> None: ...
    async def create_part(
        self,
        *,
        part_id: str,
        message_id: str,
        session_id: str,
        part_type: str,
        data: dict[str, object],
    ) -> None: ...


def is_overflow(total_tokens: int, model: ModelInfo) -> bool:
    """Check context overflow threshold at 80% of model context window."""
    return total_tokens > int(model.context_limit * 0.8)


async def prune(session_id: str, model: ModelInfo, db: CompactionDBProtocol) -> None:
    """Prune old tool outputs and append compaction marker part."""
    messages = await db.get_messages(session_id)
    if not messages:
        return

    protected_tokens = 0
    for message in reversed(messages):
        message_id = str(message["id"])
        parts = await db.get_message_parts(message_id)
        for part in parts:
            data = part.get("data")
            if not isinstance(data, dict):
                continue
            if data.get("type") == "tool" and isinstance(data.get("output"), str):
                output = str(data["output"])
                protected_tokens += max(1, len(output) // 4)
                if protected_tokens > PRUNE_PROTECT:
                    data["output"] = "[compacted]"
                    await db.update_part(str(part["id"]), data=data)

    latest_message_id = str(messages[-1]["id"])
    await db.create_part(
        part_id=ulid_str(),
        message_id=latest_message_id,
        session_id=session_id,
        part_type="compaction",
        data={"type": "compaction", "summary": "Context pruned by compaction."},
    )

