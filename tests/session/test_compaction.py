import asyncio

from metiscode.provider import ModelInfo
from metiscode.session.compaction import is_overflow, prune


class _FakeCompactionDB:
    def __init__(self) -> None:
        self.messages = [{"id": "m1"}, {"id": "m2"}]
        self.parts_by_message = {
            "m1": [
                {
                    "id": "p1",
                    "data": {"type": "tool", "output": "x" * 300_000},
                }
            ],
            "m2": [
                {
                    "id": "p2",
                    "data": {"type": "tool", "output": "recent"},
                }
            ],
        }
        self.updated_parts: list[tuple[str, dict[str, object]]] = []
        self.created_parts: list[dict[str, object]] = []

    async def get_messages(self, _session_id: str):  # type: ignore[no-untyped-def]
        return self.messages

    async def get_message_parts(self, message_id: str):  # type: ignore[no-untyped-def]
        return self.parts_by_message.get(message_id, [])

    async def update_part(self, part_id: str, *, data: dict[str, object] | None = None) -> None:
        self.updated_parts.append((part_id, data or {}))

    async def create_part(  # type: ignore[no-untyped-def]
        self,
        *,
        part_id,
        message_id,
        session_id,
        part_type,
        data,
    ) -> None:
        self.created_parts.append(
            {
                "part_id": part_id,
                "message_id": message_id,
                "session_id": session_id,
                "part_type": part_type,
                "data": data,
            }
        )


def _model() -> ModelInfo:
    return ModelInfo(
        id="claude-sonnet-4-20250514",
        provider_id="anthropic",
        name="Claude",
        context_limit=200_000,
        output_limit=8_192,
    )


def test_is_overflow_uses_eighty_percent_threshold() -> None:
    assert is_overflow(180_000, _model()) is True
    assert is_overflow(150_000, _model()) is False


def test_prune_compacts_old_tool_output() -> None:
    db = _FakeCompactionDB()
    asyncio.run(prune("sess_1", _model(), db))
    assert db.updated_parts
    assert db.updated_parts[0][1]["output"] == "[compacted]"


def test_prune_adds_compaction_part() -> None:
    db = _FakeCompactionDB()
    asyncio.run(prune("sess_1", _model(), db))
    assert db.created_parts
    assert db.created_parts[0]["part_type"] == "compaction"

