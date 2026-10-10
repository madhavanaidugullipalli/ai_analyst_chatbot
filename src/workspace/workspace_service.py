"""Workspace, dataset metadata, saved queries, reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from src.security.access_control import Permission, Role, has_permission
from src.security.audit import audit
from src.workspace.app_db import AppDatabase


@dataclass
class Workspace:
    id: int
    name: str
    owner_id: int
    role: str = Role.VIEWER.value


class WorkspaceService:
    def __init__(self, db: AppDatabase | None = None) -> None:
        self.db = db or AppDatabase()

    def create_workspace(self, name: str, owner_id: int) -> Workspace:
        ws_id = self.db.execute_write(
            "INSERT INTO workspaces (name, owner_id) VALUES (?, ?)",
            (name.strip(), owner_id),
        )
        self.db.execute_write(
            "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, ?)",
            (ws_id, owner_id, Role.OWNER.value),
        )
        audit("workspace.create", user_id=owner_id, workspace_id=ws_id, details={"name": name})
        return Workspace(id=ws_id, name=name, owner_id=owner_id, role=Role.OWNER.value)

    def list_workspaces(self, user_id: int) -> list[Workspace]:
        rows = self.db.execute(
            """
            SELECT w.id, w.name, w.owner_id, m.role
            FROM workspaces w
            JOIN workspace_members m ON m.workspace_id = w.id
            WHERE m.user_id = ?
            ORDER BY w.name
            """,
            (user_id,),
        )
        return [
            Workspace(id=r["id"], name=r["name"], owner_id=r["owner_id"], role=r["role"])
            for r in rows
        ]

    def get_membership(self, workspace_id: int, user_id: int) -> Optional[str]:
        row = self.db.execute_one(
            "SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, user_id),
        )
        return row["role"] if row else None

    def require_permission(
        self, workspace_id: int, user_id: int, permission: Permission
    ) -> str:
        role = self.get_membership(workspace_id, user_id)
        if not role or not has_permission(role, permission):
            raise PermissionError(f"Missing permission: {permission.value}")
        return role

    def add_member(
        self, workspace_id: int, actor_id: int, email: str, role: str
    ) -> None:
        self.require_permission(workspace_id, actor_id, Permission.MANAGE_MEMBERS)
        user = self.db.execute_one("SELECT id FROM users WHERE email = ?", (email.strip().lower(),))
        if not user:
            raise ValueError("User not found.")
        existing = self.get_membership(workspace_id, user["id"])
        if existing:
            self.db.execute_write(
                "UPDATE workspace_members SET role = ? WHERE workspace_id = ? AND user_id = ?",
                (role, workspace_id, user["id"]),
            )
        else:
            self.db.execute_write(
                "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, ?)",
                (workspace_id, user["id"], role),
            )
        audit(
            "workspace.add_member",
            user_id=actor_id,
            workspace_id=workspace_id,
            details={"email": email, "role": role},
        )

    def register_dataset_meta(
        self,
        workspace_id: int,
        owner_id: int,
        name: str,
        table_name: str,
        row_count: int,
        column_count: int,
        source_type: str = "upload",
        file_path: str | None = None,
    ) -> int:
        return self.db.execute_write(
            """
            INSERT INTO datasets
            (workspace_id, name, table_name, source_type, file_path, row_count, column_count, owner_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workspace_id,
                name,
                table_name,
                source_type,
                file_path,
                row_count,
                column_count,
                owner_id,
            ),
        )

    def list_datasets(self, workspace_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM datasets WHERE workspace_id = ? ORDER BY created_at DESC",
            (workspace_id,),
        )
        return [dict(r) for r in rows]

    def save_query(
        self,
        workspace_id: int,
        user_id: int,
        title: str,
        sql: str,
        question: str = "",
    ) -> int:
        return self.db.execute_write(
            """
            INSERT INTO saved_queries (workspace_id, user_id, title, question, sql)
            VALUES (?, ?, ?, ?, ?)
            """,
            (workspace_id, user_id, title, question, sql),
        )

    def list_saved_queries(self, workspace_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM saved_queries WHERE workspace_id = ? ORDER BY created_at DESC",
            (workspace_id,),
        )
        return [dict(r) for r in rows]

    def save_conversation_turn(
        self,
        workspace_id: int,
        user_id: int,
        role: str,
        content: str,
        sql: str = "",
    ) -> None:
        self.db.execute_write(
            """
            INSERT INTO conversation_turns (workspace_id, user_id, role, content, sql)
            VALUES (?, ?, ?, ?, ?)
            """,
            (workspace_id, user_id, role, content, sql),
        )

    def list_conversation(self, workspace_id: int, user_id: int, limit: int = 50) -> list[dict]:
        rows = self.db.execute(
            """
            SELECT * FROM conversation_turns
            WHERE workspace_id = ? AND user_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (workspace_id, user_id, limit),
        )
        return [dict(r) for r in reversed(rows)]

    def save_report_meta(
        self,
        workspace_id: int,
        user_id: int,
        title: str,
        path: str,
        fmt: str,
    ) -> int:
        return self.db.execute_write(
            """
            INSERT INTO reports (workspace_id, user_id, title, path, format)
            VALUES (?, ?, ?, ?, ?)
            """,
            (workspace_id, user_id, title, path, fmt),
        )

    def list_reports(self, workspace_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM reports WHERE workspace_id = ? ORDER BY created_at DESC",
            (workspace_id,),
        )
        return [dict(r) for r in rows]
