"""Mapping helpers for Harbor projects."""

from __future__ import annotations

from typing import Iterable, Mapping

from integrations.harbor.models import HarborProject, PortProjectEntity


def map_project(
    project: HarborProject,
    membership: Mapping[str, Iterable[str] | Iterable[Mapping[str, str]]] | None = None,
) -> PortProjectEntity:
    project_name = project.get("project_name") or project.get("name")
    if not isinstance(project_name, str) or not project_name:
        raise ValueError("project_name is required for Harbor project mapping")

    display_name = project.get("display_name") or project_name
    public = bool(project.get("public", False))
    visibility = _normalize_visibility(project.get("visibility"), public)
    repository_count = int(project.get("repository_count") or 0)
    owner = project.get("owner")

    member_usernames: list[str] = []
    member_roles: list[dict[str, str]] = []

    project_members = project.get("members") or []
    if isinstance(project_members, list):
        member_usernames.extend(
            str(username) for username in project_members if username
        )

    raw_roles = project.get("member_roles") or []
    if isinstance(raw_roles, list):
        for role in raw_roles:
            username = role.get("username") if isinstance(role, dict) else None
            role_name = role.get("role") if isinstance(role, dict) else None
            if username:
                member_roles.append({"username": username, "role": role_name or ""})

    if membership:
        usernames = membership.get("usernames")
        if isinstance(usernames, Iterable):
            member_usernames.extend(str(username) for username in usernames if username)

        members = membership.get("members")
        if isinstance(members, Iterable):
            for entry in members:
                if not isinstance(entry, Mapping):
                    continue
                username = entry.get("username")
                if not username:
                    continue
                role = entry.get("role") or ""
                member_roles.append({"username": str(username), "role": str(role)})

    member_usernames = sorted({username for username in member_usernames})
    member_roles = _deduplicate_roles(member_roles)

    return PortProjectEntity(
        project_name=project_name,
        display_name=str(display_name),
        public=public,
        visibility=visibility,
        repository_count=repository_count,
        owner=owner if isinstance(owner, str) else None,
        member_usernames=member_usernames,
        member_roles=member_roles,
    )


def _normalize_visibility(value: object, public: bool) -> str:
    if isinstance(value, str) and value:
        lower = value.lower()
        if lower in {"public", "private"}:
            return lower
    return "public" if public else "private"


def _deduplicate_roles(roles: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for role in roles:
        username = role.get("username")
        role_name = role.get("role", "")
        if not username:
            continue
        key = (username, role_name)
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"username": username, "role": role_name})
    deduped.sort(key=lambda value: (value.get("username", ""), value.get("role", "")))
    return deduped
