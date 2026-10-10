"""Optional PostgreSQL analytical source (Phase 8)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

import pandas as pd

from config.settings import settings


@dataclass
class PostgresTableInfo:
    schema: str
    name: str
    full_name: str


class PostgresSourceError(Exception):
    pass


class PostgresSource:
    """Read-only helper for approved Postgres tables via DuckDB postgres_scanner or pandas."""

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or settings.postgres_dsn
        if not self.dsn:
            raise PostgresSourceError("POSTGRES_DSN is not configured.")

    def enabled(self) -> bool:
        return bool(settings.postgres_enabled and self.dsn)

    def list_tables(self, schema: str = "public") -> list[PostgresTableInfo]:
        try:
            import psycopg2
        except ImportError as exc:
            raise PostgresSourceError(
                "psycopg2-binary is required for Postgres sources. "
                "Install it from requirements.txt."
            ) from exc

        sql = """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE' AND table_schema = %s
            ORDER BY table_name
        """
        with psycopg2.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (schema,))
                rows = cur.fetchall()
        return [
            PostgresTableInfo(schema=r[0], name=r[1], full_name=f"{r[0]}.{r[1]}")
            for r in rows
        ]

    def fetch_table(
        self, table: str, schema: str = "public", limit: int = 100_000
    ) -> pd.DataFrame:
        try:
            import psycopg2
        except ImportError as exc:
            raise PostgresSourceError("psycopg2-binary is required.") from exc

        # Identifier safety: allow only simple names
        if not table.replace("_", "").isalnum() or not schema.replace("_", "").isalnum():
            raise PostgresSourceError("Invalid schema/table name.")

        query = f'SELECT * FROM "{schema}"."{table}" LIMIT {int(limit)}'
        with psycopg2.connect(self.dsn) as conn:
            return pd.read_sql_query(query, conn)

    def connection_summary(self) -> dict[str, Any]:
        parsed = urlparse(self.dsn)
        return {
            "host": parsed.hostname or "",
            "port": parsed.port or 5432,
            "database": (parsed.path or "").lstrip("/"),
            "user": parsed.username or "",
        }
