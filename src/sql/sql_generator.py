"""Natural language → SQL generation with extraction and validation retries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from src.llm.llm_service import LLMService, LLMUnavailableError
from src.llm.prompts import SQL_SYSTEM_PROMPT, build_sql_repair_prompt, build_sql_user_prompt
from src.sql.sql_validator import ValidationOutcome, validate_sql

_CANNOT = re.compile(r"^\s*CANNOT_ANSWER\s*:\s*(.+)$", re.IGNORECASE | re.DOTALL)
_FENCE = re.compile(r"```(?:sql)?\s*([\s\S]*?)```", re.IGNORECASE)


@dataclass
class SQLGenerationResult:
    ok: bool
    sql: str = ""
    normalized_sql: str = ""
    message: str = ""
    cannot_answer: bool = False
    raw_llm: str = ""
    attempts: int = 0
    validation: Optional[ValidationOutcome] = None
    errors: list[str] = field(default_factory=list)


def extract_sql(text: str) -> str:
    """Pull SQL out of an LLM response (fences, prose, or plain)."""
    if not text:
        return ""
    stripped = text.strip()
    cannot = _CANNOT.match(stripped)
    if cannot:
        return stripped

    fence = _FENCE.search(stripped)
    if fence:
        return fence.group(1).strip().rstrip(";")

    # Prefer a line that starts with SELECT / WITH
    lines = stripped.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*(SELECT|WITH)\b", line, re.IGNORECASE):
            start = i
            break
    if start is not None:
        chunk = "\n".join(lines[start:]).strip()
        # Stop at trailing explanation paragraphs after a blank line following SQL
        parts = re.split(r"\n\s*\n", chunk, maxsplit=1)
        return parts[0].strip().rstrip(";")

    return stripped.rstrip(";")


class SQLGenerator:
    def __init__(self, llm: LLMService, max_attempts: int = 3) -> None:
        self.llm = llm
        self.max_attempts = max_attempts

    def generate(
        self,
        schema_text: str,
        question: str,
        allowed_tables: set[str] | list[str],
        history: str = "",
    ) -> SQLGenerationResult:
        if not self.llm.available:
            return SQLGenerationResult(
                ok=False,
                message=self.llm.status_message,
            )

        errors: list[str] = []
        raw = ""
        sql = ""

        for attempt in range(1, self.max_attempts + 1):
            try:
                if attempt == 1:
                    user = build_sql_user_prompt(schema_text, question, history)
                    raw = self.llm.complete(SQL_SYSTEM_PROMPT, user).text
                else:
                    user = build_sql_repair_prompt(
                        schema_text, question, sql or raw, errors[-1]
                    )
                    raw = self.llm.complete(SQL_SYSTEM_PROMPT, user).text
            except LLMUnavailableError as exc:
                return SQLGenerationResult(ok=False, message=str(exc), attempts=attempt)
            except Exception as exc:  # noqa: BLE001
                return SQLGenerationResult(
                    ok=False,
                    message=f"LLM request failed: {exc}",
                    attempts=attempt,
                    raw_llm=raw,
                    errors=errors,
                )

            cannot = _CANNOT.match(raw.strip())
            if cannot:
                return SQLGenerationResult(
                    ok=False,
                    cannot_answer=True,
                    message=cannot.group(1).strip(),
                    raw_llm=raw,
                    attempts=attempt,
                )

            sql = extract_sql(raw)
            outcome = validate_sql(sql, allowed_tables=allowed_tables)
            if outcome.ok:
                return SQLGenerationResult(
                    ok=True,
                    sql=outcome.sql,
                    normalized_sql=outcome.normalized_sql,
                    message="OK",
                    raw_llm=raw,
                    attempts=attempt,
                    validation=outcome,
                )

            errors.append(outcome.message)

        return SQLGenerationResult(
            ok=False,
            sql=sql,
            message=errors[-1] if errors else "SQL generation failed.",
            raw_llm=raw,
            attempts=self.max_attempts,
            errors=errors,
        )
