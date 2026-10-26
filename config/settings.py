"""Application settings loaded from environment variables."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    import streamlit as st

    if hasattr(st, "secrets"):
        for k, v in st.secrets.items():
            if isinstance(v, (str, int, float, bool)):
                k_str = str(k)
                if k_str not in os.environ:
                    os.environ[k_str] = str(v)
                if k_str.upper() not in os.environ:
                    os.environ[k_str.upper()] = str(v)
            elif hasattr(v, "items"):
                for sub_k, sub_v in v.items():
                    combo = f"{k}_{sub_k}".upper()
                    if combo not in os.environ:
                        os.environ[combo] = str(sub_v)
except Exception:
    pass

# Fallback: check .streamlit/secrets.toml directly in case TOML parsing had minor syntax issues
import re

for _sp in (
    Path(".streamlit/secrets.toml"),
    Path.home() / ".streamlit" / "secrets.toml",
):
    try:
        if _sp.is_file():
            _content = _sp.read_text(encoding="utf-8")
            _m = re.search(
                r'(?:GEMINI_API_KEY|GOOGLE_API_KEY|api_key)\s*=\s*["\']?([a-zA-Z0-9_\-\.]+)',
                _content,
                re.IGNORECASE,
            )
            if _m and "GEMINI_API_KEY" not in os.environ:
                os.environ["GEMINI_API_KEY"] = _m.group(1).strip()
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM (Gemini is the active default)
    llm_provider: str = "gemini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"

    # Limits
    max_upload_mb: int = 25
    query_timeout_seconds: int = 30
    max_result_rows: int = 10_000
    max_sql_attempts: int = 3
    duckdb_path: str = ":memory:"

    # Auth / workspaces (SQLite app DB by default)
    auth_enabled: bool = True
    app_db_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'app.db').as_posix()}"
    session_secret: str = "dev-change-me-in-production"
    default_workspace_name: str = "Personal"
    allow_guest_mode: bool = True

    # Optional Postgres analytical source (Phase 8)
    postgres_enabled: bool = False
    postgres_dsn: str = ""

    # Paths
    allowed_extensions: tuple[str, ...] = (".csv", ".xlsx", ".xls")
    data_dir: Path = PROJECT_ROOT / "data"
    uploads_dir: Path = PROJECT_ROOT / "data" / "uploads"
    reports_dir: Path = PROJECT_ROOT / "data" / "reports"
    logs_dir: Path = PROJECT_ROOT / "logs"
    sample_dataset: Path = PROJECT_ROOT / "data" / "sample_sales.csv"


settings = Settings()
settings.uploads_dir.mkdir(parents=True, exist_ok=True)
settings.reports_dir.mkdir(parents=True, exist_ok=True)
settings.logs_dir.mkdir(parents=True, exist_ok=True)
settings.data_dir.mkdir(parents=True, exist_ok=True)
