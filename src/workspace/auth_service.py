"""User registration and login."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config.settings import settings
from src.security.audit import audit
from src.security.passwords import hash_password, verify_password
from src.workspace.app_db import AppDatabase
from src.workspace.workspace_service import WorkspaceService


@dataclass
class User:
    id: int
    email: str
    display_name: str


class AuthService:
    def __init__(self, db: AppDatabase | None = None) -> None:
        self.db = db or AppDatabase()
        self.workspaces = WorkspaceService(self.db)

    def register(self, email: str, password: str, display_name: str) -> User:
        email = email.strip().lower()
        display_name = display_name.strip() or email.split("@")[0]
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if self.db.execute_one("SELECT id FROM users WHERE email = ?", (email,)):
            raise ValueError("An account with that email already exists.")

        user_id = self.db.execute_write(
            "INSERT INTO users (email, display_name, password_hash) VALUES (?, ?, ?)",
            (email, display_name, hash_password(password)),
        )
        self.workspaces.create_workspace(
            name=settings.default_workspace_name,
            owner_id=user_id,
        )
        audit("user.register", user_id=user_id, details={"email": email})
        return User(id=user_id, email=email, display_name=display_name)

    def login(self, email: str, password: str) -> User:
        email = email.strip().lower()
        row = self.db.execute_one("SELECT * FROM users WHERE email = ?", (email,))
        if not row or not verify_password(password, row["password_hash"]):
            audit("user.login", success=False, details={"email": email})
            raise ValueError("Invalid email or password.")
        audit("user.login", user_id=row["id"], details={"email": email})
        return User(id=row["id"], email=row["email"], display_name=row["display_name"])

    def get_user(self, user_id: int) -> Optional[User]:
        row = self.db.execute_one("SELECT * FROM users WHERE id = ?", (user_id,))
        if not row:
            return None
        return User(id=row["id"], email=row["email"], display_name=row["display_name"])
