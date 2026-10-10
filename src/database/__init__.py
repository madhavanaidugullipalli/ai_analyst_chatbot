"""Database package — lazy exports to avoid circular imports with sql_validator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.database.database import AnalyticsDatabase
from src.database.dataset_registry import DatasetRegistry

if TYPE_CHECKING:
    from src.database.query_executor import QueryExecutor, QueryResult

__all__ = [
    "AnalyticsDatabase",
    "DatasetRegistry",
    "QueryExecutor",
    "QueryResult",
]


def __getattr__(name: str):
    if name in {"QueryExecutor", "QueryResult"}:
        from src.database.query_executor import QueryExecutor, QueryResult

        return {"QueryExecutor": QueryExecutor, "QueryResult": QueryResult}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
