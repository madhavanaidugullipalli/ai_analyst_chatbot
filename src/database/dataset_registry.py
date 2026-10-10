"""Manage multiple registered analytical tables in one DuckDB session."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from src.data.data_profiler import profile_dataframe
from src.data.schema_inspector import schema_from_dataframe
from src.database.database import AnalyticsDatabase


@dataclass
class DatasetEntry:
    name: str
    table_name: str
    source_type: str
    rows: int
    columns: int
    profile: dict[str, Any] = field(default_factory=dict)
    schema: dict[str, Any] = field(default_factory=dict)


class DatasetRegistry:
    def __init__(self, db: AnalyticsDatabase | None = None) -> None:
        self.db = db or AnalyticsDatabase()
        self.entries: dict[str, DatasetEntry] = {}
        self.active_table: Optional[str] = None
        self.dataframes: dict[str, pd.DataFrame] = {}

    def register(
        self,
        df: pd.DataFrame,
        name: str,
        table_name: str = "data",
        source_type: str = "upload",
        make_active: bool = True,
    ) -> DatasetEntry:
        registered = self.db.register_dataframe(df, table_name=table_name)
        profile = profile_dataframe(df, name=name)
        schema = schema_from_dataframe(df, table_name=registered)
        entry = DatasetEntry(
            name=name,
            table_name=registered,
            source_type=source_type,
            rows=len(df),
            columns=len(df.columns),
            profile=profile,
            schema=schema,
        )
        self.entries[registered] = entry
        self.dataframes[registered] = df
        if make_active or self.active_table is None:
            self.active_table = registered
        return entry

    def set_active(self, table_name: str) -> DatasetEntry:
        if table_name not in self.entries:
            raise KeyError(f"Unknown table: {table_name}")
        self.active_table = table_name
        return self.entries[table_name]

    def get_active(self) -> Optional[DatasetEntry]:
        if not self.active_table:
            return None
        return self.entries.get(self.active_table)

    def get_active_df(self) -> Optional[pd.DataFrame]:
        if not self.active_table:
            return None
        return self.dataframes.get(self.active_table)

    def list_tables(self) -> list[str]:
        return list(self.entries.keys())

    def combined_schema_text(self) -> str:
        parts = []
        for entry in self.entries.values():
            from src.data.schema_inspector import schema_prompt_text

            parts.append(schema_prompt_text(entry.schema))
        return "\n\n".join(parts)
