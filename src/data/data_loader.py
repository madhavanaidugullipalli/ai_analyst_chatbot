"""Load CSV and Excel files into pandas DataFrames."""

from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO, Union

import pandas as pd

from src.security.file_validation import validate_upload

PathOrBuffer = Union[str, Path, BinaryIO, bytes]


class DataLoadError(Exception):
    """Raised when a dataset cannot be loaded."""


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        str(c).strip().replace(" ", "_").replace("-", "_") for c in df.columns
    ]
    # Deduplicate column names
    seen: dict[str, int] = {}
    new_cols: list[str] = []
    for col in df.columns:
        if col in seen:
            seen[col] += 1
            new_cols.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            new_cols.append(col)
    df.columns = new_cols
    return df


def load_tabular_file(
    source: PathOrBuffer,
    filename: str | None = None,
    size_bytes: int | None = None,
) -> pd.DataFrame:
    """
    Load a CSV or Excel file into a DataFrame.

    ``source`` may be a filesystem path, bytes, or a file-like object.
    When loading from bytes/buffer, pass ``filename`` and preferably ``size_bytes``.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise DataLoadError(f"File not found: {path}")
        filename = filename or path.name
        size_bytes = size_bytes if size_bytes is not None else path.stat().st_size
        check = validate_upload(filename, size_bytes)
        if not check.ok:
            raise DataLoadError(check.message)
        suffix = check.suffix
        try:
            if suffix == ".csv":
                df = _read_csv(path)
            else:
                df = pd.read_excel(path, engine="openpyxl")
        except Exception as exc:  # noqa: BLE001 — surface as DataLoadError
            raise DataLoadError(f"Failed to parse file: {exc}") from exc
    else:
        if not filename:
            raise DataLoadError("filename is required when loading from a buffer.")
        if size_bytes is None:
            if isinstance(source, bytes):
                size_bytes = len(source)
            else:
                size_bytes = 1  # defer size; extension still checked
        check = validate_upload(filename, max(size_bytes, 1))
        if not check.ok:
            raise DataLoadError(check.message)
        suffix = check.suffix
        try:
            if isinstance(source, bytes):
                buffer = io.BytesIO(source)
            else:
                buffer = source
            if suffix == ".csv":
                df = _read_csv(buffer)
            else:
                df = pd.read_excel(buffer, engine="openpyxl")
        except Exception as exc:  # noqa: BLE001
            raise DataLoadError(f"Failed to parse file: {exc}") from exc

    if df.empty and len(df.columns) == 0:
        raise DataLoadError("File contains no columns.")

    return _normalize_columns(df)


def _read_csv(source: PathOrBuffer) -> pd.DataFrame:
    """Try common encodings when reading CSV."""
    encodings = ("utf-8", "utf-8-sig", "latin-1", "cp1252")
    last_error: Exception | None = None
    for enc in encodings:
        try:
            if isinstance(source, (str, Path)):
                return pd.read_csv(source, encoding=enc)
            if isinstance(source, bytes):
                return pd.read_csv(io.BytesIO(source), encoding=enc)
            # file-like: reset if possible
            if hasattr(source, "seek"):
                source.seek(0)
            return pd.read_csv(source, encoding=enc)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except Exception:
            raise
    raise DataLoadError(f"Could not decode CSV: {last_error}")
