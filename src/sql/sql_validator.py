"""Parse and validate SQL before execution. Prompting alone is not the security boundary."""

from __future__ import annotations

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from src.database.query_limits import max_result_rows
from src.sql.query_policy import (
    ALLOWED_STATEMENT_TYPES,
    FORBIDDEN_KEYWORDS,
    FORBIDDEN_STATEMENT_TYPES,
)


@dataclass
class ValidationOutcome:
    ok: bool
    message: str
    sql: str = ""
    normalized_sql: str = ""
    tables_referenced: list[str] = field(default_factory=list)


def validate_sql(
    sql: str,
    allowed_tables: set[str] | list[str] | None = None,
    dialect: str = "duckdb",
) -> ValidationOutcome:
    if not sql or not sql.strip():
        return ValidationOutcome(False, "SQL query is empty.")

    cleaned = sql.strip().rstrip(";")
    upper = cleaned.upper()

    for kw in FORBIDDEN_KEYWORDS:
        if kw in upper:
            return ValidationOutcome(
                False, f"Forbidden keyword or feature: {kw}", sql=cleaned
            )

    try:
        statements = sqlglot.parse(cleaned, read=dialect)
    except ParseError as exc:
        return ValidationOutcome(False, f"SQL parse error: {exc}", sql=cleaned)

    if not statements:
        return ValidationOutcome(False, "No SQL statement found.", sql=cleaned)
    if len(statements) > 1:
        return ValidationOutcome(
            False, "Only a single SQL statement is allowed.", sql=cleaned
        )

    statement = statements[0]
    if statement is None:
        return ValidationOutcome(False, "Empty statement.", sql=cleaned)

    stmt_type = type(statement).__name__.upper()
    # sqlglot uses class names like Select, Insert
    root_kind = statement.key.upper() if hasattr(statement, "key") else stmt_type

    if root_kind in FORBIDDEN_STATEMENT_TYPES or stmt_type in FORBIDDEN_STATEMENT_TYPES:
        return ValidationOutcome(
            False, f"Statement type '{root_kind}' is not allowed.", sql=cleaned
        )

    if not isinstance(statement, (exp.Select, exp.Union, exp.With)):
        # Allow DESCRIBE / SHOW for exploration in Phase 1
        if root_kind not in {"DESCRIBE", "SHOW", "EXPLAIN", "SELECT", "WITH", "UNION"}:
            if root_kind not in ALLOWED_STATEMENT_TYPES:
                return ValidationOutcome(
                    False,
                    f"Only read-only SELECT queries are allowed (got {root_kind}).",
                    sql=cleaned,
                )

    # Reject DML/DDL hidden inside CTEs via Command nodes
    for node in statement.walk():
        if isinstance(
            node,
            (
                exp.Insert,
                exp.Update,
                exp.Delete,
                exp.Drop,
                exp.Create,
                exp.Alter,
                exp.Command,
            ),
        ):
            return ValidationOutcome(
                False,
                f"Disallowed SQL construct: {type(node).__name__}",
                sql=cleaned,
            )

    tables = {
        t.name.lower()
        for t in statement.find_all(exp.Table)
        if t.name
    }

    if allowed_tables is not None:
        allowed = {t.lower() for t in allowed_tables}
        unknown = tables - allowed
        if unknown:
            return ValidationOutcome(
                False,
                f"Query references unauthorized table(s): {', '.join(sorted(unknown))}",
                sql=cleaned,
                tables_referenced=sorted(tables),
            )

    try:
        normalized = statement.sql(dialect=dialect)
    except Exception:  # noqa: BLE001
        normalized = cleaned

    # Enforce LIMIT if missing on SELECT
    if isinstance(statement, (exp.Select, exp.With, exp.Union)):
        if not statement.find(exp.Limit):
            limit_n = max_result_rows()
            normalized = f"SELECT * FROM ({normalized}) AS _q LIMIT {limit_n}"

    return ValidationOutcome(
        True,
        "OK",
        sql=cleaned,
        normalized_sql=normalized,
        tables_referenced=sorted(tables),
    )
