"""Generate dataset profiles from pandas DataFrames."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def profile_dataframe(df: pd.DataFrame, name: str = "dataset") -> dict[str, Any]:
    n_rows, n_cols = df.shape
    missing_total = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())

    columns: list[dict[str, Any]] = []
    numeric_cols: list[str] = []
    categorical_cols: list[str] = []
    datetime_cols: list[str] = []

    for col in df.columns:
        series = df[col]
        missing = int(series.isna().sum())
        dtype_name = str(series.dtype)
        inferred = _infer_kind(series)

        col_info: dict[str, Any] = {
            "name": col,
            "dtype": dtype_name,
            "inferred_type": inferred,
            "missing_count": missing,
            "missing_pct": round(100.0 * missing / n_rows, 2) if n_rows else 0.0,
            "unique_count": int(series.nunique(dropna=True)),
        }

        if inferred == "numeric":
            numeric_cols.append(col)
            non_null = pd.to_numeric(series, errors="coerce").dropna()
            if len(non_null):
                col_info.update(
                    {
                        "min": float(non_null.min()),
                        "max": float(non_null.max()),
                        "mean": float(non_null.mean()),
                        "median": float(non_null.median()),
                        "std": float(non_null.std()) if len(non_null) > 1 else 0.0,
                    }
                )
        elif inferred == "datetime":
            datetime_cols.append(col)
            parsed = pd.to_datetime(series, errors="coerce").dropna()
            if len(parsed):
                col_info["min"] = str(parsed.min())
                col_info["max"] = str(parsed.max())
        else:
            categorical_cols.append(col)
            top = series.astype(str).value_counts(dropna=True).head(5)
            col_info["top_values"] = {str(k): int(v) for k, v in top.items()}

        columns.append(col_info)

    return {
        "name": name,
        "rows": n_rows,
        "columns": n_cols,
        "missing_values": missing_total,
        "duplicate_rows": duplicate_rows,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "datetime_columns": datetime_cols,
        "column_details": columns,
    }


def _infer_kind(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    # Try coerce datetime for object columns with date-like values
    if series.dtype == object or pd.api.types.is_string_dtype(series):
        sample = series.dropna().head(50)
        if len(sample) == 0:
            return "categorical"
        # Prefer ISO-like dates to avoid noisy format inference warnings
        sample_str = sample.astype(str)
        if sample_str.str.match(r"^\d{4}-\d{2}-\d{2}").mean() >= 0.8:
            return "datetime"
        parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        if parsed.notna().mean() >= 0.8:
            return "datetime"
        numeric = pd.to_numeric(sample, errors="coerce")
        if numeric.notna().mean() >= 0.8:
            return "numeric"
    return "categorical"


def profile_summary_text(profile: dict[str, Any]) -> str:
    return (
        f"**{profile['name']}** — "
        f"{profile['rows']:,} rows × {profile['columns']} columns | "
        f"Missing: {profile['missing_values']:,} | "
        f"Duplicates: {profile['duplicate_rows']:,}"
    )
