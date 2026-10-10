from pathlib import Path

from src.security.access_control import Permission, Role, has_permission
from src.security.passwords import hash_password, verify_password
from src.workspace.app_db import AppDatabase
from src.workspace.auth_service import AuthService


def test_password_roundtrip():
    hashed = hash_password("secret-pass")
    assert verify_password("secret-pass", hashed)
    assert not verify_password("wrong", hashed)


def test_roles():
    assert has_permission(Role.ANALYST, Permission.UPLOAD)
    assert not has_permission(Role.VIEWER, Permission.UPLOAD)
    assert has_permission(Role.OWNER, Permission.MANAGE_WORKSPACE)


def test_register_login(tmp_path: Path):
    db = AppDatabase(tmp_path / "test_app.db")
    auth = AuthService(db)
    user = auth.register("analyst@example.com", "password123", "Analyst")
    assert user.id > 0
    spaces = auth.workspaces.list_workspaces(user.id)
    assert len(spaces) == 1
    logged = auth.login("analyst@example.com", "password123")
    assert logged.email == "analyst@example.com"
