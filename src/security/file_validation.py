"""Upload validation — extension and size checks (content verified on load)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.settings import settings


@dataclass
class ValidationResult:
    ok: bool
    message: str
    suffix: str = ""


def validate_upload(filename: str, size_bytes: int) -> ValidationResult:
    if not filename or not filename.strip():
        return ValidationResult(False, "Filename is required.")

    suffix = Path(filename).suffix.lower()
    if suffix not in settings.allowed_extensions:
        allowed = ", ".join(settings.allowed_extensions)
        return ValidationResult(
            False,
            f"Unsupported file type '{suffix}'. Allowed: {allowed}",
            suffix=suffix,
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size_bytes <= 0:
        return ValidationResult(False, "File is empty.", suffix=suffix)
    if size_bytes > max_bytes:
        return ValidationResult(
            False,
            f"File exceeds the {settings.max_upload_mb} MB upload limit.",
            suffix=suffix,
        )

    return ValidationResult(True, "OK", suffix=suffix)
