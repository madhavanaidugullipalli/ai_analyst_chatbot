from pathlib import Path

from src.data.data_loader import load_tabular_file
from src.database.dataset_registry import DatasetRegistry

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_sales.csv"


def test_multi_dataset_registry():
    df = load_tabular_file(SAMPLE)
    reg = DatasetRegistry()
    a = reg.register(df, name="sales.csv", table_name="sales")
    b = reg.register(df.head(10), name="subset.csv", table_name="subset")
    assert set(reg.list_tables()) == {"sales", "subset"}
    assert reg.active_table == "subset"
    reg.set_active("sales")
    assert reg.get_active().table_name == a.table_name
    assert "sales" in reg.combined_schema_text()
    assert b.rows == 10
