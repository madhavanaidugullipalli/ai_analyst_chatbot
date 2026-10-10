"""Role-based access control for workspaces."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    OWNER = "owner"
    ADMINISTRATOR = "administrator"
    ANALYST = "analyst"
    VIEWER = "viewer"


ROLE_RANK = {
    Role.VIEWER: 1,
    Role.ANALYST: 2,
    Role.ADMINISTRATOR: 3,
    Role.OWNER: 4,
}


class Permission(str, Enum):
    VIEW_DATA = "view_data"
    RUN_QUERY = "run_query"
    UPLOAD = "upload"
    GENERATE_REPORT = "generate_report"
    MANAGE_MEMBERS = "manage_members"
    MANAGE_SOURCES = "manage_sources"
    MANAGE_WORKSPACE = "manage_workspace"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.VIEWER: {
        Permission.VIEW_DATA,
        Permission.RUN_QUERY,
        Permission.GENERATE_REPORT,
    },
    Role.ANALYST: {
        Permission.VIEW_DATA,
        Permission.RUN_QUERY,
        Permission.UPLOAD,
        Permission.GENERATE_REPORT,
    },
    Role.ADMINISTRATOR: {
        Permission.VIEW_DATA,
        Permission.RUN_QUERY,
        Permission.UPLOAD,
        Permission.GENERATE_REPORT,
        Permission.MANAGE_MEMBERS,
        Permission.MANAGE_SOURCES,
    },
    Role.OWNER: set(Permission),
}


def has_permission(role: str | Role, permission: Permission) -> bool:
    try:
        role_enum = Role(role) if isinstance(role, str) else role
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(role_enum, set())


def can_assign_role(actor_role: str | Role, target_role: str | Role) -> bool:
    try:
        actor = Role(actor_role) if isinstance(actor_role, str) else actor_role
        target = Role(target_role) if isinstance(target_role, str) else target_role
    except ValueError:
        return False
    return ROLE_RANK[actor] >= ROLE_RANK[target] and ROLE_RANK[actor] >= ROLE_RANK[Role.ADMINISTRATOR]
