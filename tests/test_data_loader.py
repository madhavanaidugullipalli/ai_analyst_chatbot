from pathlib import Path

import pytest

from src.data.data_loader import DataLoadError, load_tabular_file
from src.security.file_validation import validate_upload

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "sample_sales.csv"


def test_validate_reject_bad_extension():
    result = validate_upload("notes.txt", 100)
    assert not result.ok


def test_validate_reject_oversized():
    result = validate_upload("big.csv", 100 * 1024 * 1024)
    assert not result.ok


def test_load_sample_csv():
    df = load_tabular_file(SAMPLE)
    assert len(df) == 30
    assert "sales_amount" in df.columns
    assert "product_name" in df.columns


def test_load_missing_file():
    with pytest.raises(DataLoadError):
        load_tabular_file(ROOT / "data" / "does_not_exist.csv")
