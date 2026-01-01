"""Mapping helpers for Harbor users."""

from __future__ import annotations

from integrations.harbor.models import HarborUser, PortUserEntity


def map_user(user: HarborUser) -> PortUserEntity:
    username = user.get("username")
    if not isinstance(username, str) or not username:
        raise ValueError("user username is required")

    display_name = user.get("display_name") or username
    email = user.get("email")
    creation_time = user.get("creation_time")
    update_time = user.get("update_time")
    is_robot = bool(user.get("is_robot", False))
    is_admin = bool(user.get("is_admin", False))

    projects = _to_string_list(user.get("projects"))
    project_roles_raw = user.get("project_roles") or []
    project_roles = [
        {"project": entry.get("project", ""), "role": entry.get("role", "")}
        for entry in project_roles_raw
        if isinstance(entry, dict)
    ]

    role_names = _to_string_list(user.get("role_names"))

    return PortUserEntity(
        username=username,
        display_name=str(display_name),
        email=email if isinstance(email, str) else None,
        creation_time=creation_time if isinstance(creation_time, str) else None,
        update_time=update_time if isinstance(update_time, str) else None,
        is_robot=is_robot,
        is_admin=is_admin,
        projects=projects,
        project_roles=project_roles,
        role_names=role_names,
    )


def _to_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, (str, int, float)):
            result.append(str(item))
    return result
