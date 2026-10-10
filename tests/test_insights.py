from pathlib import Path

from src.analytics.data_quality import analyze_data_quality
from src.analytics.insights import generate_insights
from src.data.data_loader import load_tabular_file

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_sales.csv"


def test_insights_on_sample():
    df = load_tabular_file(SAMPLE)
    result = generate_insights(df)
    assert result["summary"]
    assert result["suggested_questions"]
    assert any("region" in q.lower() or "sales" in q.lower() for q in result["suggested_questions"])


def test_data_quality_on_sample():
    df = load_tabular_file(SAMPLE)
    quality = analyze_data_quality(df)
    assert 0 <= quality["score"] <= 100
    assert quality["checks"]["rows"] == 30
