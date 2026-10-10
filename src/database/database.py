"""DuckDB connection and dataset registration."""

from __future__ import annotations

import re
from typing import Optional

import duckdb
import pandas as pd

from config.settings import settings

_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class AnalyticsDatabase:
    """In-memory (or file) DuckDB store for uploaded analytical datasets."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or settings.duckdb_path
        self._conn = duckdb.connect(self.path)
        self._tables: dict[str, int] = {}

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._conn

    def list_tables(self) -> list[str]:
        return sorted(self._tables.keys())

    def register_dataframe(self, df: pd.DataFrame, table_name: str = "data") -> str:
        name = self._sanitize_table_name(table_name)
        # Replace existing registration
        if name in self._tables:
            self._conn.execute(f'DROP TABLE IF EXISTS "{name}"')
        self._conn.register("_tmp_df", df)
        self._conn.execute(f'CREATE TABLE "{name}" AS SELECT * FROM _tmp_df')
        self._conn.unregister("_tmp_df")
        self._tables[name] = len(df)
        return name

    def table_exists(self, table_name: str) -> bool:
        return table_name in self._tables

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _sanitize_table_name(name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name.strip())
        if not cleaned or not _SAFE_IDENT.match(cleaned):
            cleaned = "data"
        return cleaned.lower()
