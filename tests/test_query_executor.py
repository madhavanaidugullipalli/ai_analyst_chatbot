from pathlib import Path

from src.data.data_loader import load_tabular_file
from src.database.database import AnalyticsDatabase
from src.database.query_executor import QueryExecutor

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_sales.csv"


def test_execute_aggregation():
    df = load_tabular_file(SAMPLE)
    db = AnalyticsDatabase()
    db.register_dataframe(df, "sales")
    executor = QueryExecutor(db)
    result = executor.execute(
        "SELECT region, SUM(sales_amount) AS total FROM sales GROUP BY region ORDER BY total DESC"
    )
    assert result.success
    assert result.row_count == 4
    assert "total" in result.dataframe.columns
    db.close()


def test_reject_then_no_execute():
    df = load_tabular_file(SAMPLE)
    db = AnalyticsDatabase()
    db.register_dataframe(df, "sales")
    executor = QueryExecutor(db)
    result = executor.execute("DELETE FROM sales")
    assert not result.success
    db.close()
