"""Inspect table/column schema for prompts and UI."""

from __future__ import annotations

from typing import Any

import pandas as pd


def schema_from_dataframe(df: pd.DataFrame, table_name: str = "data") -> dict[str, Any]:
    columns = []
    for col in df.columns:
        series = df[col]
        columns.append(
            {
                "name": col,
                "dtype": str(series.dtype),
                "nullable": bool(series.isna().any()),
                "sample_values": [
                    _json_safe(v) for v in series.dropna().head(3).tolist()
                ],
            }
        )
    return {
        "table_name": table_name,
        "columns": columns,
        "row_count": len(df),
    }


def schema_prompt_text(schema: dict[str, Any]) -> str:
    lines = [f"Table: {schema['table_name']}", "Columns:"]
    for col in schema["columns"]:
        lines.append(f"  - {col['name']}: {col['dtype']}")
    return "\n".join(lines)


def _json_safe(value: Any) -> Any:
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:  # noqa: BLE001
            return str(value)
    if isinstance(value, (pd.Timestamp,)):
        return str(value)
    return value
