"""Data-quality analysis — report issues; do not auto-correct without consent."""

from __future__ import annotations

from typing import Any

import pandas as pd


def analyze_data_quality(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or df.empty:
        return {
            "issues": [{"severity": "critical", "message": "Dataset is empty."}],
            "score": 0,
            "checks": {},
        }

    issues: list[dict[str, Any]] = []
    n = len(df)

    # Missing values
    missing = df.isna().sum()
    for col, count in missing.items():
        if count == 0:
            continue
        pct = 100.0 * count / n
        severity = "high" if pct >= 20 else "medium" if pct >= 5 else "low"
        issues.append(
            {
                "type": "missing_values",
                "column": col,
                "count": int(count),
                "pct": round(pct, 2),
                "severity": severity,
                "message": f"Column '{col}' has {count} missing values ({pct:.1f}%).",
            }
        )

    # Duplicates
    dup = int(df.duplicated().sum())
    if dup:
        issues.append(
            {
                "type": "duplicate_rows",
                "count": dup,
                "severity": "medium" if dup / n < 0.05 else "high",
                "message": f"{dup} fully duplicate row(s) found.",
            }
        )

    # Mixed / suspicious types in object columns
    for col in df.select_dtypes(include=["object", "string"]).columns:
        sample = df[col].dropna().head(200)
        if sample.empty:
            continue
        numeric_like = pd.to_numeric(sample, errors="coerce").notna().mean()
        if 0.2 < numeric_like < 0.9:
            issues.append(
                {
                    "type": "mixed_types",
                    "column": col,
                    "severity": "medium",
                    "message": (
                        f"Column '{col}' appears mixed (≈{numeric_like:.0%} numeric-like)."
                    ),
                }
            )

    # Invalid dates
    for col in df.columns:
        if "date" not in col.lower() and "time" not in col.lower():
            continue
        parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
        invalid = int(df[col].notna().sum() - parsed.notna().sum())
        if invalid > 0:
            issues.append(
                {
                    "type": "invalid_dates",
                    "column": col,
                    "count": invalid,
                    "severity": "medium",
                    "message": f"Column '{col}' has {invalid} value(s) that are not valid dates.",
                }
            )

    # Extreme numeric values (z-score style)
    for col in df.select_dtypes(include="number").columns:
        series = df[col].dropna()
        if len(series) < 10:
            continue
        mean, std = series.mean(), series.std()
        if std == 0 or pd.isna(std):
            continue
        extremes = int(((series - mean).abs() > 4 * std).sum())
        if extremes:
            issues.append(
                {
                    "type": "extreme_values",
                    "column": col,
                    "count": extremes,
                    "severity": "low",
                    "message": (
                        f"Column '{col}' has {extremes} observation(s) beyond 4σ from the mean."
                    ),
                }
            )

    # Constant columns
    for col in df.columns:
        if df[col].nunique(dropna=True) <= 1:
            issues.append(
                {
                    "type": "constant_column",
                    "column": col,
                    "severity": "low",
                    "message": f"Column '{col}' has little or no variation.",
                }
            )

    # Score: start 100, subtract weighted issues
    penalty = 0
    weights = {"critical": 40, "high": 15, "medium": 8, "low": 3}
    for issue in issues:
        penalty += weights.get(issue.get("severity", "low"), 3)
    score = max(0, min(100, 100 - penalty))

    return {
        "issues": issues,
        "score": score,
        "checks": {
            "rows": n,
            "columns": len(df.columns),
            "missing_cells": int(df.isna().sum().sum()),
            "duplicate_rows": dup,
            "issue_count": len(issues),
        },
    }
