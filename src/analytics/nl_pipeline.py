"""End-to-end natural-language analytics: question → SQL → execute → explain."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from src.analytics.result_analyzer import fallback_explanation, result_preview
from src.conversation.conversation_manager import ConversationManager
from src.data.schema_inspector import schema_prompt_text
from src.database.query_executor import QueryExecutor, QueryResult
from src.llm.llm_service import LLMService
from src.security.audit import app_logger
from src.sql.sql_generator import SQLGenerationResult, SQLGenerator

log = app_logger("ai_data_analyst.nl")


@dataclass
class AnalysisAnswer:
    success: bool
    question: str
    explanation: str = ""
    sql: str = ""
    validated_sql: str = ""
    dataframe: Optional[pd.DataFrame] = None
    row_count: int = 0
    duration_ms: float = 0.0
    error: str = ""
    cannot_answer: bool = False
    needs_clarification: bool = False
    llm_attempts: int = 0
    generation: Optional[SQLGenerationResult] = None
    query: Optional[QueryResult] = None
    meta: dict[str, Any] = field(default_factory=dict)


class NLAnalyticsPipeline:
    def __init__(
        self,
        executor: QueryExecutor,
        llm: LLMService | None = None,
        conversation: ConversationManager | None = None,
        max_sql_attempts: int = 3,
    ) -> None:
        self.executor = executor
        self.llm = llm or LLMService()
        self.conversation = conversation or ConversationManager()
        self.sql_generator = SQLGenerator(self.llm, max_attempts=max_sql_attempts)

    def ask(
        self,
        question: str,
        schema: dict[str, Any],
        allowed_tables: list[str] | None = None,
        schema_text: str | None = None,
    ) -> AnalysisAnswer:
        question = (question or "").strip()
        if not question:
            return AnalysisAnswer(
                success=False, question=question, error="Please enter a question."
            )

        columns = [c["name"] for c in schema.get("columns", [])]
        clarification = self.conversation.needs_clarification(question, columns)
        if clarification and not self.conversation.looks_like_follow_up(question):
            self.conversation.add_user(question)
            self.conversation.add_assistant(clarification)
            return AnalysisAnswer(
                success=False,
                question=question,
                explanation=clarification,
                error=clarification,
                needs_clarification=True,
            )

        enriched = self.conversation.enrich_question(question)
        tables = allowed_tables or self.executor.db.list_tables()
        text = schema_text or schema_prompt_text(schema)
        history = self._history_text()

        self.conversation.add_user(question)
        log.info("nl.ask question=%r tables=%s", question, tables)

        generation = self.sql_generator.generate(
            schema_text=text,
            question=enriched,
            allowed_tables=tables,
            history=history,
        )

        if not generation.ok:
            msg = generation.message
            if generation.cannot_answer:
                explanation = f"I cannot answer that with the available columns: {msg}"
            else:
                explanation = msg
            self.conversation.add_assistant(explanation, sql=generation.sql)
            return AnalysisAnswer(
                success=False,
                question=question,
                explanation=explanation,
                error=msg,
                cannot_answer=generation.cannot_answer,
                sql=generation.sql,
                llm_attempts=generation.attempts,
                generation=generation,
            )

        query = self.executor.execute(generation.normalized_sql or generation.sql)
        if not query.success:
            repaired = self.sql_generator.generate(
                schema_text=text,
                question=(
                    f"{enriched}\n\nPrevious SQL failed with: {query.error}. "
                    "Fix the SQL."
                ),
                allowed_tables=tables,
                history=history,
            )
            if repaired.ok:
                generation = repaired
                query = self.executor.execute(repaired.normalized_sql or repaired.sql)

        if not query.success:
            explanation = f"Query failed after validation: {query.error}"
            self.conversation.add_assistant(explanation, sql=query.sql)
            return AnalysisAnswer(
                success=False,
                question=question,
                explanation=explanation,
                error=query.error,
                sql=generation.sql,
                validated_sql=query.validated_sql,
                duration_ms=query.duration_ms,
                llm_attempts=generation.attempts,
                generation=generation,
                query=query,
            )

        explanation = self._explain(question, query.validated_sql or query.sql, query)
        self.conversation.add_assistant(
            explanation,
            sql=query.validated_sql,
            row_count=query.row_count,
        )
        return AnalysisAnswer(
            success=True,
            question=question,
            explanation=explanation,
            sql=generation.sql,
            validated_sql=query.validated_sql,
            dataframe=query.dataframe,
            row_count=query.row_count,
            duration_ms=query.duration_ms,
            llm_attempts=generation.attempts,
            generation=generation,
            query=query,
        )

    def _explain(self, question: str, sql: str, query: QueryResult) -> str:
        preview = result_preview(query.dataframe)
        if self.llm.available:
            try:
                return self.llm.explain_result(question, sql, preview).strip()
            except Exception:  # noqa: BLE001
                pass
        return fallback_explanation(question, query.dataframe, query.row_count)

    def _history_text(self) -> str:
        parts = []
        for turn in self.conversation.recent_context(6):
            role = turn["role"]
            content = turn["content"]
            sql = turn.get("sql") or ""
            line = f"{role}: {content}"
            if sql:
                line += f"\n  sql: {sql}"
            parts.append(line)
        return "\n".join(parts)
