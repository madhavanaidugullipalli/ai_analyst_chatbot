"""Chart recommendations and Plotly figure builders."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def recommend_chart(df: pd.DataFrame) -> Optional[str]:
    if df is None or df.empty or len(df.columns) < 1:
        return None

    numeric = df.select_dtypes(include="number").columns.tolist()
    non_numeric = [c for c in df.columns if c not in numeric]

    if len(df) == 1 and len(numeric) >= 1:
        return None  # single scalar row — table is enough

    if len(non_numeric) >= 1 and len(numeric) >= 1 and len(df) <= 50:
        return "bar"

    if len(numeric) >= 1 and len(df) >= 5 and len(non_numeric) == 0:
        return "histogram"

    if len(numeric) >= 2 and len(df) >= 5:
        return "scatter"

    if len(non_numeric) >= 1 and len(numeric) >= 1 and len(df) <= 8:
        return "pie"

    return None


def build_plotly_figure(
    df: pd.DataFrame, chart_type: str | None = None
) -> Optional[go.Figure]:
    chart_type = chart_type or recommend_chart(df)
    if not chart_type or df is None or df.empty:
        return None

    numeric = df.select_dtypes(include="number").columns.tolist()
    non_numeric = [c for c in df.columns if c not in numeric]

    try:
        if chart_type == "bar" and non_numeric and numeric:
            fig = px.bar(df, x=non_numeric[0], y=numeric[0], title=None)
        elif chart_type == "line" and non_numeric and numeric:
            fig = px.line(df, x=non_numeric[0], y=numeric[0], markers=True)
        elif chart_type == "histogram" and numeric:
            fig = px.histogram(df, x=numeric[0])
        elif chart_type == "scatter" and len(numeric) >= 2:
            fig = px.scatter(df, x=numeric[0], y=numeric[1])
        elif chart_type == "pie" and non_numeric and numeric and len(df) <= 12:
            fig = px.pie(df, names=non_numeric[0], values=numeric[0])
        else:
            return None
        fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=400)
        return fig
    except Exception:  # noqa: BLE001
        return None


def chart_options_for_df(df: pd.DataFrame) -> list[str]:
    options = ["auto", "none"]
    numeric = df.select_dtypes(include="number").columns.tolist()
    non_numeric = [c for c in df.columns if c not in numeric]
    if non_numeric and numeric:
        options.extend(["bar", "line", "pie"])
    if numeric:
        options.append("histogram")
    if len(numeric) >= 2:
        options.append("scatter")
    return options
