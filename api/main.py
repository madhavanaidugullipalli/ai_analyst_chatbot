"""
Optional FastAPI backend for programmatic access (Phase 10).

Run: uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from src.data.data_loader import load_tabular_file
from src.database.dataset_registry import DatasetRegistry
from src.database.query_executor import QueryExecutor
from src.llm.llm_service import LLMService
from src.analytics.nl_pipeline import NLAnalyticsPipeline
from src.conversation.conversation_manager import ConversationManager
from src.sql.sql_validator import validate_sql

app = FastAPI(
    title="AI Data Analyst API",
    version="1.0.0",
    description="Programmatic access to validated analytics queries.",
)

_registry = DatasetRegistry()
_executor = QueryExecutor(_registry.db)
_llm = LLMService()
_conversation = ConversationManager()
_pipeline = NLAnalyticsPipeline(_executor, _llm, _conversation)


class SQLRequest(BaseModel):
    sql: str
    allowed_tables: Optional[list[str]] = None


class AskRequest(BaseModel):
    question: str
    table: Optional[str] = None


class LoadSampleResponse(BaseModel):
    table: str
    rows: int
    columns: int


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_available": _llm.available,
        "tables": _registry.list_tables(),
    }


@app.post("/datasets/sample", response_model=LoadSampleResponse)
def load_sample() -> LoadSampleResponse:
    df = load_tabular_file(settings.sample_dataset)
    entry = _registry.register(df, name="sample_sales.csv", table_name="sales")
    return LoadSampleResponse(
        table=entry.table_name, rows=entry.rows, columns=entry.columns
    )


@app.post("/sql/validate")
def sql_validate(body: SQLRequest) -> dict[str, Any]:
    tables = body.allowed_tables or _registry.list_tables()
    outcome = validate_sql(body.sql, allowed_tables=tables)
    return {
        "ok": outcome.ok,
        "message": outcome.message,
        "normalized_sql": outcome.normalized_sql,
        "tables_referenced": outcome.tables_referenced,
    }


@app.post("/sql/execute")
def sql_execute(body: SQLRequest) -> dict[str, Any]:
    result = _executor.execute(body.sql, allowed_tables=body.allowed_tables)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return {
        "row_count": result.row_count,
        "duration_ms": result.duration_ms,
        "sql": result.validated_sql,
        "columns": list(result.dataframe.columns),
        "rows": result.dataframe.head(500).to_dict(orient="records"),
    }


@app.post("/ask")
def ask(body: AskRequest) -> dict[str, Any]:
    entry = _registry.get_active()
    if body.table:
        try:
            entry = _registry.set_active(body.table)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    if entry is None:
        raise HTTPException(status_code=400, detail="No dataset loaded. POST /datasets/sample first.")
    if not _llm.available:
        raise HTTPException(status_code=503, detail=_llm.status_message)
    answer = _pipeline.ask(
        body.question,
        schema=entry.schema,
        allowed_tables=_registry.list_tables(),
        schema_text=_registry.combined_schema_text(),
    )
    payload: dict[str, Any] = {
        "success": answer.success,
        "explanation": answer.explanation,
        "sql": answer.validated_sql or answer.sql,
        "row_count": answer.row_count,
        "error": answer.error,
    }
    if answer.success and answer.dataframe is not None:
        payload["rows"] = answer.dataframe.head(200).to_dict(orient="records")
    return payload
