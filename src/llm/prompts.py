"""Prompt templates for NL→SQL and explanations."""

SQL_SYSTEM_PROMPT = """You are a careful data analyst that writes DuckDB SQL.
Rules:
- Respond with ONLY one of:
  1) A single SELECT (or WITH ... SELECT) statement, or
  2) CANNOT_ANSWER: <short reason>
- No markdown fences, no commentary, no trailing explanation.
- Use only the tables and columns provided in the schema.
- Do not invent columns or tables.
- Prefer clear column aliases for aggregations.
- Never use INSERT, UPDATE, DELETE, DROP, CREATE, COPY, ATTACH, PRAGMA, or extensions.
"""

EXPLANATION_SYSTEM_PROMPT = """You explain analytical query results for business users.
Rules:
- Ground every factual claim in the provided result values.
- Do not invent numbers, rankings, or trends that are not in the result.
- Distinguish calculated facts from interpretation.
- Do not claim that correlation proves causation.
- Keep the explanation to 2–4 short sentences.
"""


def build_sql_user_prompt(schema_text: str, question: str, history: str = "") -> str:
    parts = [
        "Schema:",
        schema_text,
        "",
        f"Question: {question}",
    ]
    if history:
        parts.extend(["", "Recent conversation:", history])
    parts.extend(["", "SQL:"])
    return "\n".join(parts)


def build_sql_repair_prompt(
    schema_text: str,
    question: str,
    bad_sql: str,
    error: str,
) -> str:
    return (
        f"Schema:\n{schema_text}\n\n"
        f"Question: {question}\n\n"
        f"Previous SQL (invalid):\n{bad_sql}\n\n"
        f"Validation/execution error:\n{error}\n\n"
        "Return a corrected single SELECT (or WITH ... SELECT) for DuckDB. "
        "If impossible, reply with CANNOT_ANSWER: <reason>."
    )


def build_explanation_prompt(question: str, sql: str, result_preview: str) -> str:
    return (
        f"Question: {question}\n"
        f"SQL: {sql}\n"
        f"Result preview:\n{result_preview}\n"
    )
