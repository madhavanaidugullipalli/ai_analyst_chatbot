"""Format query results for LLM explanations and UI previews."""

from __future__ import annotations

from typing import Optional

import pandas as pd


def result_preview(df: Optional[pd.DataFrame], max_rows: int = 15) -> str:
    if df is None:
        return "(no dataframe)"
    if df.empty:
        return "(empty result — 0 rows)"
    preview = df.head(max_rows)
    return preview.to_string(index=False)


def fallback_explanation(
    question: str,
    df: Optional[pd.DataFrame],
    row_count: int,
) -> str:
    """Deterministic summary when the LLM is unavailable."""
    if df is None:
        return "The query did not return a result table."
    if df.empty:
        return (
            f"For “{question}”, the query ran successfully but returned no matching rows."
        )
    if row_count == 1 and len(df.columns) <= 3:
        parts = [f"{col}={df.iloc[0][col]}" for col in df.columns]
        return f"Answer: {', '.join(parts)}."
    return (
        f"The query returned {row_count} row(s) and {len(df.columns)} column(s). "
        "Inspect the result table for details."
    )
