"""Server app facade."""

from __future__ import annotations

from dataclasses import dataclass

from metiscode.server import routes
from metiscode.session import SessionDB


@dataclass(slots=True)
class App:
    db: SessionDB

    async def list_sessions(self) -> list[dict[str, object]]:
        return await routes.list_sessions(self.db)

    async def create_session(
        self,
        model: str | None = None,
        agent: str | None = None,
    ) -> dict[str, object]:
        return await routes.create_session(self.db, model=model, agent=agent)

    async def health(self) -> dict[str, str]:
        return routes.health()


def create_app(*, project_id: str = "global") -> App:
    return App(db=SessionDB(project_id=project_id))
