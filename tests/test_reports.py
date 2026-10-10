import pandas as pd

from src.reports.report_generator import ReportGenerator, ReportPayload


def test_report_markdown_and_excel(tmp_path):
    payload = ReportPayload(
        title="Sales Summary",
        question="Total by region?",
        dataset_name="sample",
        table_name="sales",
        sql="SELECT region, SUM(sales_amount) FROM sales GROUP BY region",
        explanation="East leads in this sample.",
        dataframe=pd.DataFrame({"region": ["East", "West"], "total": [100, 80]}),
        insights=["East is highest."],
        follow_ups=["Break down by category."],
    )
    gen = ReportGenerator(output_dir=tmp_path)
    paths = gen.save(payload, formats=["md", "html", "xlsx"])
    assert paths["md"].exists()
    assert "Sales Summary" in paths["md"].read_text(encoding="utf-8")
    assert paths["html"].exists()
    assert paths["xlsx"].exists()
    assert len(paths["xlsx"].read_bytes()) > 100
