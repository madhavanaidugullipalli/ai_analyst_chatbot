"""Query resource limits."""

from config.settings import settings


def max_result_rows() -> int:
    return settings.max_result_rows


def query_timeout_seconds() -> int:
    return settings.query_timeout_seconds
