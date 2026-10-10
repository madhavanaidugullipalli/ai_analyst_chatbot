"""SQLite application database for users, workspaces, and persistence."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from config.settings import PROJECT_ROOT, settings


def _sqlite_path() -> Path:
    url = settings.app_db_url
    if url.startswith("sqlite:///"):
        return Path(url.replace("sqlite:///", "", 1))
    return PROJECT_ROOT / "data" / "app.db"


class AppDatabase:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _sqlite_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS workspaces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    owner_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY(owner_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS workspace_members (
                    workspace_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    PRIMARY KEY (workspace_id, user_id),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'upload',
                    file_path TEXT,
                    row_count INTEGER DEFAULT 0,
                    column_count INTEGER DEFAULT 0,
                    owner_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                    FOREIGN KEY(owner_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS saved_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    question TEXT,
                    sql TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sql TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    path TEXT NOT NULL,
                    format TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            cur = conn.execute(sql, params)
            if cur.description:
                return list(cur.fetchall())
            return []

    def execute_one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        rows = self.execute(sql, params)
        return rows[0] if rows else None

    def execute_write(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self.connect() as conn:
            cur = conn.execute(sql, params)
            return int(cur.lastrowid or 0)
