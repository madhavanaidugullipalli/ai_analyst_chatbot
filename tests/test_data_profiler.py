from pathlib import Path

from src.data.data_loader import load_tabular_file
from src.data.data_profiler import profile_dataframe

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_sales.csv"


def test_profile_sample():
    df = load_tabular_file(SAMPLE)
    profile = profile_dataframe(df, name="sales")
    assert profile["rows"] == 30
    assert profile["columns"] == 8
    assert "sales_amount" in profile["numeric_columns"]
    assert "region" in profile["categorical_columns"]
    assert profile["missing_values"] == 0
