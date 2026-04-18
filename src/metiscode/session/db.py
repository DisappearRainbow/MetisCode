"""SQLite session database service."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any


def _now_ms() -> int:
    return int(time.time() * 1000)


def default_db_path(project_id: str) -> Path:
    """Get default database path for a project."""
    env_path = os.getenv("METISCODE_DB_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()
    base = Path.home() / ".metiscode" / "data"
    return base / f"{project_id}.db"


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


class SessionDB:
    """Async wrapper around sqlite3 for session/message/part/todo storage."""

    def __init__(self, *, project_id: str, db_path: Path | None = None) -> None:
        self.project_id = project_id
        self.db_path = db_path or default_db_path(project_id)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        """Create tables and indexes if not exists."""

        def _init() -> None:
            connection = _connect(self.db_path)
            try:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS session (
                      id TEXT PRIMARY KEY,
                      project_id TEXT NOT NULL,
                      parent_id TEXT,
                      slug TEXT NOT NULL,
                      directory TEXT NOT NULL,
                      title TEXT NOT NULL,
                      version INTEGER NOT NULL DEFAULT 1,
                      permission TEXT,
                      time_created INTEGER NOT NULL,
                      time_updated INTEGER NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS message (
                      id TEXT PRIMARY KEY,
                      session_id TEXT NOT NULL,
                      role TEXT NOT NULL,
                      time_created INTEGER NOT NULL,
                      data TEXT NOT NULL,
                      FOREIGN KEY(session_id) REFERENCES session(id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS part (
                      id TEXT PRIMARY KEY,
                      message_id TEXT NOT NULL,
                      session_id TEXT NOT NULL,
                      type TEXT NOT NULL,
                      time_created INTEGER NOT NULL,
                      data TEXT NOT NULL,
                      FOREIGN KEY(message_id) REFERENCES message(id) ON DELETE CASCADE,
                      FOREIGN KEY(session_id) REFERENCES session(id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS todo (
                      id TEXT PRIMARY KEY,
                      session_id TEXT NOT NULL,
                      content TEXT NOT NULL,
                      status TEXT NOT NULL,
                      priority INTEGER NOT NULL,
                      time_created INTEGER NOT NULL,
                      FOREIGN KEY(session_id) REFERENCES session(id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS permission_request (
                      id TEXT PRIMARY KEY,
                      session_id TEXT NOT NULL,
                      tool TEXT NOT NULL,
                      pattern TEXT NOT NULL,
                      action TEXT NOT NULL,
                      time_created INTEGER NOT NULL,
                      FOREIGN KEY(session_id) REFERENCES session(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_message_session_id ON message(session_id);
                    CREATE INDEX IF NOT EXISTS idx_part_session_id ON part(session_id);
                    CREATE INDEX IF NOT EXISTS idx_part_message_id ON part(message_id);
                    CREATE INDEX IF NOT EXISTS idx_todo_session_id ON todo(session_id);
                    CREATE INDEX IF NOT EXISTS idx_permission_request_session_id
                      ON permission_request(session_id);
                    """
                )
                connection.commit()
            finally:
                connection.close()

        await asyncio.to_thread(_init)

    async def create_session(
        self,
        *,
        session_id: str,
        slug: str,
        directory: str,
        title: str,
        parent_id: str | None = None,
        version: int = 1,
        permission: dict[str, Any] | None = None,
    ) -> None:
        now = _now_ms()

        def _create() -> None:
            connection = _connect(self.db_path)
            try:
                connection.execute(
                    """
                    INSERT INTO session (
                      id, project_id, parent_id, slug, directory, title,
                      version, permission, time_created, time_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        self.project_id,
                        parent_id,
                        slug,
                        directory,
                        title,
                        version,
                        json.dumps(permission) if permission is not None else None,
                        now,
                        now,
                    ),
                )
                connection.commit()
            finally:
                connection.close()

        await asyncio.to_thread(_create)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        def _get() -> dict[str, Any] | None:
            connection = _connect(self.db_path)
            try:
                row = connection.execute(
                    "SELECT * FROM session WHERE id = ?",
                    (session_id,),
                ).fetchone()
            finally:
                connection.close()
            if row is None:
                return None
            result = dict(row)
            if result["permission"]:
                result["permission"] = json.loads(result["permission"])
            else:
                result["permission"] = None
            return result

        return await asyncio.to_thread(_get)

    async def list_sessions(self, project_id: str | None = None) -> list[dict[str, Any]]:
        selected_project = project_id or self.project_id

        def _list() -> list[dict[str, Any]]:
            connection = _connect(self.db_path)
            try:
                rows = connection.execute(
                    """
                    SELECT * FROM session
                    WHERE project_id = ?
                    ORDER BY time_updated DESC, id DESC
                    """,
                    (selected_project,),
                ).fetchall()
            finally:
                connection.close()
            result: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                item["permission"] = json.loads(item["permission"]) if item["permission"] else None
                result.append(item)
            return result

        return await asyncio.to_thread(_list)

    async def update_session(self, session_id: str, **fields: Any) -> None:
        if not fields:
            return
        allowed = {"parent_id", "slug", "directory", "title", "version", "permission"}
        invalid = [key for key in fields if key not in allowed]
        if invalid:
            raise ValueError(f"Unsupported fields for session update: {invalid}")

        updates = dict(fields)
        if "permission" in updates:
            value = updates["permission"]
            updates["permission"] = json.dumps(value) if value is not None else None
        updates["time_updated"] = _now_ms()

        columns = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values())
        values.append(session_id)

        def _update() -> None:
            connection = _connect(self.db_path)
            try:
                connection.execute(f"UPDATE session SET {columns} WHERE id = ?", values)
                connection.commit()
            finally:
                connection.close()

        await asyncio.to_thread(_update)

    async def delete_session(self, session_id: str) -> None:
        def _delete() -> None:
            connection = _connect(self.db_path)
            try:
                connection.execute("DELETE FROM session WHERE id = ?", (session_id,))
                connection.commit()
            finally:
                connection.close()

        await asyncio.to_thread(_delete)

    async def create_message(
        self,
        *,
        message_id: str,
        session_id: str,
        role: str,
        data: dict[str, Any],
    ) -> None:
        now = _now_ms()

        def _create() -> None:
            connection = _connect(self.db_path)
            try:
                connection.execute(
                    """
                    INSERT INTO message (id, session_id, role, time_created, data)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (message_id, session_id, role, now, json.dumps(data)),
                )
                connection.commit()
            finally:
                connection.close()

        await asyncio.to_thread(_create)

    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        def _get() -> list[dict[str, Any]]:
            connection = _connect(self.db_path)
            try:
                rows = connection.execute(
                    """
                    SELECT * FROM message
                    WHERE session_id = ?
                    ORDER BY time_created ASC, id ASC
                    """,
                    (session_id,),
                ).fetchall()
            finally:
                connection.close()
            result: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                item["data"] = json.loads(item["data"])
                result.append(item)
            return result

        return await asyncio.to_thread(_get)

    async def create_part(
        self,
        *,
        part_id: str,
        message_id: str,
        session_id: str,
        part_type: str,
        data: dict[str, Any],
    ) -> None:
        now = _now_ms()

        def _create() -> None:
            connection = _connect(self.db_path)
            try:
                connection.execute(
                    """
                    INSERT INTO part (id, message_id, session_id, type, time_created, data)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (part_id, message_id, session_id, part_type, now, json.dumps(data)),
                )
                connection.commit()
            finally:
                connection.close()

        await asyncio.to_thread(_create)

    async def update_part(
        self,
        part_id: str,
        *,
        data: dict[str, Any] | None = None,
        part_type: str | None = None,
    ) -> None:
        updates: dict[str, Any] = {}
        if data is not None:
            updates["data"] = json.dumps(data)
        if part_type is not None:
            updates["type"] = part_type
        if not updates:
            return

        columns = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values())
        values.append(part_id)

        def _update() -> None:
            connection = _connect(self.db_path)
            try:
                connection.execute(f"UPDATE part SET {columns} WHERE id = ?", values)
                connection.commit()
            finally:
                connection.close()

        await asyncio.to_thread(_update)

    async def get_message_parts(self, message_id: str) -> list[dict[str, Any]]:
        def _get() -> list[dict[str, Any]]:
            connection = _connect(self.db_path)
            try:
                rows = connection.execute(
                    """
                    SELECT * FROM part
                    WHERE message_id = ?
                    ORDER BY time_created ASC, id ASC
                    """,
                    (message_id,),
                ).fetchall()
            finally:
                connection.close()
            result: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                item["data"] = json.loads(item["data"])
                result.append(item)
            return result

        return await asyncio.to_thread(_get)

    async def create_todo(
        self,
        *,
        todo_id: str,
        session_id: str,
        content: str,
        status: str,
        priority: int,
    ) -> None:
        now = _now_ms()

        def _create() -> None:
            connection = _connect(self.db_path)
            try:
                connection.execute(
                    """
                    INSERT INTO todo (id, session_id, content, status, priority, time_created)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (todo_id, session_id, content, status, priority, now),
                )
                connection.commit()
            finally:
                connection.close()

        await asyncio.to_thread(_create)

    async def update_todo(self, todo_id: str, **fields: Any) -> None:
        if not fields:
            return
        allowed = {"content", "status", "priority"}
        invalid = [key for key in fields if key not in allowed]
        if invalid:
            raise ValueError(f"Unsupported fields for todo update: {invalid}")

        columns = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values())
        values.append(todo_id)

        def _update() -> None:
            connection = _connect(self.db_path)
            try:
                connection.execute(f"UPDATE todo SET {columns} WHERE id = ?", values)
                connection.commit()
            finally:
                connection.close()

        await asyncio.to_thread(_update)

    async def get_todos(self, session_id: str) -> list[dict[str, Any]]:
        def _get() -> list[dict[str, Any]]:
            connection = _connect(self.db_path)
            try:
                rows = connection.execute(
                    """
                    SELECT * FROM todo
                    WHERE session_id = ?
                    ORDER BY time_created ASC, id ASC
                    """,
                    (session_id,),
                ).fetchall()
            finally:
                connection.close()
            return [dict(row) for row in rows]

        return await asyncio.to_thread(_get)
