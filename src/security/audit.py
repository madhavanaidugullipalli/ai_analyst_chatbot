"""Lightweight security / audit event logging."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings

_logger = logging.getLogger("ai_data_analyst.audit")
if not _logger.handlers:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(settings.logs_dir / "audit.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)


def audit(
    event: str,
    *,
    user_id: int | None = None,
    workspace_id: int | None = None,
    success: bool = True,
    details: dict[str, Any] | None = None,
) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "success": success,
        "details": details or {},
    }
    _logger.info(json.dumps(payload, default=str))


def app_logger(name: str = "ai_data_analyst") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        path = Path(settings.logs_dir) / "app.log"
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
