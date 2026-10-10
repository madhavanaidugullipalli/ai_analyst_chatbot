"""Generate analytical reports as Markdown, HTML, and Excel."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from config.settings import settings


@dataclass
class ReportPayload:
    title: str
    question: str = ""
    dataset_name: str = ""
    table_name: str = ""
    methodology: str = "Natural-language question translated to validated DuckDB SQL."
    sql: str = ""
    explanation: str = ""
    limitations: str = (
        "Results reflect only the loaded dataset and the executed query. "
        "Correlation does not imply causation."
    )
    follow_ups: list[str] = field(default_factory=list)
    dataframe: Optional[pd.DataFrame] = None
    profile_summary: str = ""
    insights: list[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )


class ReportGenerator:
    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or settings.reports_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def to_markdown(self, payload: ReportPayload) -> str:
        lines = [
            f"# {payload.title}",
            "",
            f"**Generated:** {payload.generated_at}",
            f"**Dataset:** {payload.dataset_name or '—'} (table `{payload.table_name or '—'}`)",
            "",
            "## Business question",
            payload.question or "—",
            "",
            "## Methodology",
            payload.methodology,
            "",
        ]
        if payload.profile_summary:
            lines.extend(["## Dataset information", payload.profile_summary, ""])
        if payload.sql:
            lines.extend(["## SQL query", "```sql", payload.sql, "```", ""])
        if payload.explanation:
            lines.extend(["## Summary of findings", payload.explanation, ""])
        if payload.insights:
            lines.append("## Additional insights")
            lines.extend(f"- {i}" for i in payload.insights)
            lines.append("")
        if payload.dataframe is not None and not payload.dataframe.empty:
            lines.extend(
                [
                    "## Results",
                    "```",
                    payload.dataframe.head(50).to_string(index=False),
                    "```",
                    "",
                ]
            )
        lines.extend(["## Limitations", payload.limitations, ""])
        if payload.follow_ups:
            lines.append("## Recommended follow-up analyses")
            lines.extend(f"- {q}" for q in payload.follow_ups)
            lines.append("")
        return "\n".join(lines)

    def to_html(self, payload: ReportPayload) -> str:
        md = self.to_markdown(payload)
        # Minimal HTML wrapper (no external markdown lib required)
        body = (
            md.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        # Very light formatting
        html_body = []
        in_code = False
        for line in body.splitlines():
            if line.startswith("```"):
                if not in_code:
                    html_body.append("<pre><code>")
                    in_code = True
                else:
                    html_body.append("</code></pre>")
                    in_code = False
                continue
            if in_code:
                html_body.append(line)
                continue
            if line.startswith("# "):
                html_body.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith("## "):
                html_body.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("- "):
                html_body.append(f"<li>{line[2:]}</li>")
            elif line.startswith("**") and line.endswith("**"):
                html_body.append(f"<p><strong>{line.strip('*')}</strong></p>")
            elif line.strip() == "":
                html_body.append("")
            else:
                html_body.append(f"<p>{line}</p>")
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{payload.title}</title>"
            "<style>body{font-family:Segoe UI,sans-serif;max-width:900px;"
            "margin:2rem auto;padding:0 1rem;line-height:1.5}"
            "code,pre{background:#f4f4f4;padding:.5rem;overflow:auto}"
            "table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:.35rem}</style>"
            "</head><body>"
            + "\n".join(html_body)
            + "</body></html>"
        )

    def to_excel_bytes(self, payload: ReportPayload) -> bytes:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            meta = pd.DataFrame(
                [
                    {"field": "title", "value": payload.title},
                    {"field": "generated_at", "value": payload.generated_at},
                    {"field": "dataset", "value": payload.dataset_name},
                    {"field": "table", "value": payload.table_name},
                    {"field": "question", "value": payload.question},
                    {"field": "sql", "value": payload.sql},
                    {"field": "explanation", "value": payload.explanation},
                    {"field": "limitations", "value": payload.limitations},
                ]
            )
            meta.to_excel(writer, sheet_name="Summary", index=False)
            if payload.dataframe is not None:
                payload.dataframe.to_excel(writer, sheet_name="Results", index=False)
            if payload.insights:
                pd.DataFrame({"insight": payload.insights}).to_excel(
                    writer, sheet_name="Insights", index=False
                )
        return buffer.getvalue()

    def save(
        self, payload: ReportPayload, formats: list[str] | None = None
    ) -> dict[str, Path]:
        formats = formats or ["md", "html", "xlsx"]
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in payload.title)[:60]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base = self.output_dir / f"{safe}_{stamp}"
        paths: dict[str, Path] = {}
        if "md" in formats:
            path = Path(str(base) + ".md")
            path.write_text(self.to_markdown(payload), encoding="utf-8")
            paths["md"] = path
        if "html" in formats:
            path = Path(str(base) + ".html")
            path.write_text(self.to_html(payload), encoding="utf-8")
            paths["html"] = path
        if "xlsx" in formats:
            path = Path(str(base) + ".xlsx")
            path.write_bytes(self.to_excel_bytes(payload))
            paths["xlsx"] = path
        return paths
