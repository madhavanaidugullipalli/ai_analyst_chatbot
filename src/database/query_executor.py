"""Execute validated SQL against DuckDB."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from src.database.database import AnalyticsDatabase
from src.database.query_limits import max_result_rows, query_timeout_seconds
from src.sql.sql_validator import ValidationOutcome, validate_sql


@dataclass
class QueryResult:
    success: bool
    dataframe: Optional[pd.DataFrame] = None
    error: str = ""
    sql: str = ""
    validated_sql: str = ""
    row_count: int = 0
    duration_ms: float = 0.0
    validation: Optional[ValidationOutcome] = None
    truncated: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


class QueryExecutor:
    def __init__(self, db: AnalyticsDatabase) -> None:
        self.db = db

    def execute(
        self,
        sql: str,
        allowed_tables: list[str] | None = None,
        skip_validation: bool = False,
    ) -> QueryResult:
        tables = allowed_tables if allowed_tables is not None else self.db.list_tables()

        if skip_validation:
            outcome = ValidationOutcome(
                True, "skipped", sql=sql.strip(), normalized_sql=sql.strip()
            )
        else:
            outcome = validate_sql(sql, allowed_tables=tables)

        if not outcome.ok:
            return QueryResult(
                success=False,
                error=outcome.message,
                sql=sql,
                validation=outcome,
            )

        to_run = outcome.normalized_sql or outcome.sql
        start = time.perf_counter()
        try:
            # DuckDB Python API does not expose a portable statement timeout on all builds;
            # we still record duration and enforce row caps.
            _ = query_timeout_seconds()
            relation = self.db.connection.execute(to_run)
            df = relation.fetchdf()
            duration_ms = (time.perf_counter() - start) * 1000
            truncated = False
            limit = max_result_rows()
            if len(df) > limit:
                df = df.head(limit)
                truncated = True
            return QueryResult(
                success=True,
                dataframe=df,
                sql=outcome.sql,
                validated_sql=to_run,
                row_count=len(df),
                duration_ms=round(duration_ms, 2),
                validation=outcome,
                truncated=truncated,
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.perf_counter() - start) * 1000
            return QueryResult(
                success=False,
                error=str(exc),
                sql=outcome.sql,
                validated_sql=to_run,
                duration_ms=round(duration_ms, 2),
                validation=outcome,
            )
