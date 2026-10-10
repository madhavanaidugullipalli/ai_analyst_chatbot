"""Automated statistical insights grounded in actual data calculations."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def generate_insights(df: pd.DataFrame, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    if df is None or df.empty:
        return {
            "summary": ["Dataset is empty — no insights available."],
            "suggested_questions": [],
            "category_comparisons": [],
            "trends": [],
            "outliers": [],
        }

    numeric = df.select_dtypes(include="number").columns.tolist()
    categorical = [
        c
        for c in df.columns
        if c not in numeric
        and (pd.api.types.is_string_dtype(df[c]) or pd.api.types.is_object_dtype(df[c]))
    ]
    # Also treat low-cardinality non-numeric as categorical
    for c in df.columns:
        if c not in numeric and c not in categorical and df[c].nunique(dropna=True) <= 20:
            categorical.append(c)

    datetime_cols = []
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            datetime_cols.append(c)
        elif c not in numeric:
            parsed = pd.to_datetime(df[c], errors="coerce", format="mixed")
            if parsed.notna().mean() >= 0.8:
                datetime_cols.append(c)

    summary: list[str] = [
        f"Dataset has {len(df):,} rows and {len(df.columns)} columns.",
        f"Numeric columns: {', '.join(numeric) or 'none'}.",
        f"Categorical columns: {', '.join(categorical[:8]) or 'none'}.",
    ]
    if profile:
        summary.append(
            f"Missing values: {profile.get('missing_values', 0):,}; "
            f"duplicate rows: {profile.get('duplicate_rows', 0):,}."
        )

    category_comparisons = _category_comparisons(df, categorical, numeric)
    trends = _time_trends(df, datetime_cols, numeric)
    outliers = _outlier_notes(df, numeric)
    suggested = _suggested_questions(df, categorical, numeric, datetime_cols)

    for item in category_comparisons[:3]:
        summary.append(item["text"])
    for item in trends[:2]:
        summary.append(item["text"])
    for item in outliers[:2]:
        summary.append(item["text"])

    return {
        "summary": summary,
        "suggested_questions": suggested,
        "category_comparisons": category_comparisons,
        "trends": trends,
        "outliers": outliers,
    }


def _category_comparisons(
    df: pd.DataFrame, categorical: list[str], numeric: list[str]
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not categorical or not numeric:
        return results
    cat = categorical[0]
    num = numeric[0]
    grouped = (
        df.groupby(cat, dropna=True)[num]
        .agg(["sum", "mean", "count"])
        .sort_values("sum", ascending=False)
    )
    if grouped.empty:
        return results
    top = grouped.index[0]
    top_sum = grouped.iloc[0]["sum"]
    results.append(
        {
            "type": "category_sum",
            "category_col": cat,
            "metric_col": num,
            "top_category": str(top),
            "value": float(top_sum),
            "text": (
                f"By {num} total, '{top}' leads among {cat} values "
                f"({top_sum:,.2f})."
            ),
            "table": grouped.reset_index(),
        }
    )
    if len(grouped) >= 2:
        bottom = grouped.index[-1]
        results.append(
            {
                "type": "category_low",
                "text": (
                    f"Lowest {num} total is '{bottom}' "
                    f"({grouped.iloc[-1]['sum']:,.2f})."
                ),
            }
        )
    return results


def _time_trends(
    df: pd.DataFrame, datetime_cols: list[str], numeric: list[str]
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not datetime_cols or not numeric:
        return results
    date_col = datetime_cols[0]
    num = numeric[0]
    work = df[[date_col, num]].copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce", format="mixed")
    work = work.dropna()
    if work.empty:
        return results
    work["period"] = work[date_col].dt.to_period("M").astype(str)
    monthly = work.groupby("period")[num].sum().sort_index()
    if len(monthly) < 2:
        return results
    delta = float(monthly.iloc[-1] - monthly.iloc[-2])
    pct = (delta / abs(float(monthly.iloc[-2]))) * 100 if monthly.iloc[-2] else 0.0
    direction = "increased" if delta >= 0 else "decreased"
    results.append(
        {
            "type": "monthly_trend",
            "text": (
                f"{num} {direction} by {abs(delta):,.2f} ({pct:+.1f}%) "
                f"from {monthly.index[-2]} to {monthly.index[-1]}."
            ),
            "table": monthly.reset_index(name=num),
        }
    )
    return results


def _outlier_notes(df: pd.DataFrame, numeric: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for col in numeric[:3]:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 8:
            continue
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_out = int(((series < low) | (series > high)).sum())
        if n_out:
            results.append(
                {
                    "type": "outlier",
                    "column": col,
                    "count": n_out,
                    "text": (
                        f"{n_out} potential outlier value(s) detected in '{col}' "
                        f"using the IQR rule."
                    ),
                }
            )
    return results


def _pick_primary_categorical(categorical: list[str]) -> str | None:
    if not categorical:
        return None
    for pref in ("region", "category", "department", "segment", "type"):
        for col in categorical:
            if pref in col.lower():
                return col
    return categorical[0]


def _pick_primary_numeric(numeric: list[str]) -> str | None:
    if not numeric:
        return None
    for col in numeric:
        lower = col.lower()
        if any(k in lower for k in ("sales", "amount", "revenue", "price", "total")):
            return col
    non_id = [c for c in numeric if not c.lower().endswith("_id") and c.lower() != "id"]
    return non_id[0] if non_id else numeric[0]


def _suggested_questions(
    df: pd.DataFrame,
    categorical: list[str],
    numeric: list[str],
    datetime_cols: list[str],
) -> list[str]:
    qs: list[str] = []
    cat = _pick_primary_categorical(categorical)
    num = _pick_primary_numeric(numeric)
    if cat and num:
        qs.append(f"Which {cat} has the highest total {num}?")
        qs.append(f"Compare average {num} across {cat}.")
    if len(categorical) >= 2 and num:
        qs.append(f"Break down {num} by {cat} and {categorical[1]}.")
    if datetime_cols and num:
        qs.append(f"Show monthly {num} trend over time.")
    if num:
        qs.append(f"What is the distribution of {num}?")
    qs.append("Which columns have the most missing values?")
    return qs[:8]
