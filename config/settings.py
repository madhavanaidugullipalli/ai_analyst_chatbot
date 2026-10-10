"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

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
    gemini_model: str = "gemini-3.8-flash"

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
