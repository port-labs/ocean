from __future__ import annotations

from typing import Any, AsyncGenerator, Mapping, MutableMapping

from loguru import logger

try:  # pragma: no cover
    import httpx  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    from integrations.harbor._compat import httpx_stub as httpx  # noqa: F401

from integrations.harbor.client import HarborClient


class UsersExporter:
    """Stream Harbor users along with their project memberships."""

    USERS_PATH = "/users"
    MEMBER_PATH_TEMPLATE = "/projects/{project_id}/members"

    def __init__(
        self,
        client: HarborClient,
        *,
        project_lookup: Mapping[int, str] | None = None,
    ) -> None:
        self.client = client
        self.project_lookup: dict[int, str] = {
            int(project_id): project_name
            for project_id, project_name in (project_lookup or {}).items()
            if project_name
        }
        self._membership_cache: (
            tuple[
                dict[str, MutableMapping[str, Any]],
                dict[str, MutableMapping[str, Any]],
            ]
            | None
        ) = None

    async def iter_users(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield Harbor users with enriched membership data."""

        membership_index, _ = await self._ensure_memberships_loaded()

        async for page in self.client.iter_pages(self.USERS_PATH):
            if not page:
                continue

            transformed: list[dict[str, Any]] = []
            for item in page:
                mapped = self._transform_user(item, membership_index)
                if mapped is not None:
                    transformed.append(mapped)

            if transformed:
                logger.debug(
                    "harbor.users.page_processed",
                    count=len(transformed),
                    input_count=len(page),
                )
                yield transformed

    async def get_project_members(self, project_id: int) -> list[dict[str, Any]]:
        """Fetch raw membership data for a specific project."""

        response = await self.client.get(
            self.MEMBER_PATH_TEMPLATE.format(project_id=project_id)
        )
        payload = response.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            members = payload.get("members") or payload.get("data")
            if isinstance(members, list):
                return members
        return []

    async def membership_index(
        self,
    ) -> tuple[
        Mapping[str, Mapping[str, Any]],
        Mapping[str, Mapping[str, Any]],
    ]:
        """Return cached membership data keyed by user and by project."""

        user_index, project_index = await self._ensure_memberships_loaded()
        return user_index, project_index

    async def _ensure_memberships_loaded(
        self,
    ) -> tuple[
        dict[str, MutableMapping[str, Any]],
        dict[str, MutableMapping[str, Any]],
    ]:
        if self._membership_cache is not None:
            return self._membership_cache

        membership_by_user: dict[str, MutableMapping[str, Any]] = {}
        membership_by_project: dict[str, MutableMapping[str, Any]] = {}

        for project_id, project_name in self.project_lookup.items():
            try:
                members = await self.get_project_members(project_id)
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "harbor.memberships.fetch_failed",
                    project_id=project_id,
                    status=exc.response.status_code,
                    error=str(exc),
                )
                continue
            except httpx.HTTPError as exc:
                logger.warning(
                    "harbor.memberships.transport_error",
                    project_id=project_id,
                    error=str(exc),
                )
                continue

            if not isinstance(members, list):
                continue

            project_entry = membership_by_project.setdefault(
                project_name,
                {
                    "usernames": set(),
                    "members": set(),
                },
            )

            for member in members:
                if not isinstance(member, dict):
                    continue

                entity_type = str(
                    member.get("entity_type") or member.get("entityType") or ""
                ).lower()

                # Skip groups, only capture users and robots
                if entity_type in {"g", "group"}:
                    continue

                member_user = member.get("member_user") or member.get("memberUser")
                if isinstance(member_user, dict):
                    username = member_user.get("username")
                    user_id = member_user.get("user_id") or member_user.get("id")
                else:
                    username = member.get("entity_name") or member.get("entityName")
                    user_id = member.get("entity_id") or member.get("entityId")

                if not username:
                    continue

                role_name = member.get("role_name") or member.get("roleName")
                key_username = f"user:{username.lower()}"
                entry = membership_by_user.get(key_username)

                if entry is None:
                    entry = membership_by_user[key_username] = {
                        "projects": set(),
                        "role_names": set(),
                        "project_roles": set(),
                        "usernames": set(),
                    }
                entry["projects"].add(project_name)
                entry["usernames"].add(username)
                if role_name:
                    entry["role_names"].add(role_name)
                entry["project_roles"].add((project_name, role_name or ""))

                if user_id is not None:
                    membership_by_user[f"id:{user_id}"] = entry

                project_entry["usernames"].add(username)
                project_entry["members"].add((username, role_name or ""))

        processed_entries: set[int] = set()
        for data in membership_by_user.values():
            data_id = id(data)
            if data_id in processed_entries:
                continue
            processed_entries.add(data_id)

            data["projects"] = sorted(data["projects"])
            data["role_names"] = sorted(data["role_names"])
            data["project_roles"] = [
                {"project": project, "role": role}
                for project, role in sorted(data["project_roles"])
            ]
            data["usernames"] = sorted(data["usernames"])

        for project_name, details in membership_by_project.items():
            details["usernames"] = sorted(details["usernames"])
            details["members"] = [
                {"username": username, "role": role}
                for username, role in sorted(details["members"])
            ]

        self._membership_cache = (membership_by_user, membership_by_project)
        return self._membership_cache

    def _transform_user(
        self,
        user: Any,
        membership_index: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any] | None:
        if not isinstance(user, dict):
            return None

        username = user.get("username")
        if not isinstance(username, str) or not username:
            return None

        user_id = user.get("user_id") or user.get("id")
        key_username = f"user:{username.lower()}"
        membership = membership_index.get(key_username)
        if membership is None and user_id is not None:
            membership = membership_index.get(f"id:{user_id}")

        projects = membership.get("projects", []) if membership else []
        project_roles = membership.get("project_roles", []) if membership else []
        role_names = membership.get("role_names", []) if membership else []

        display_name = (
            user.get("realname")
            or user.get("full_name")
            or user.get("comment")
            or username
        )

        email = user.get("email")
        creation_time = user.get("creation_time") or user.get("creationTime")
        update_time = user.get("update_time") or user.get("updateTime")
        is_robot = bool(user.get("is_robot"))
        if not is_robot:
            is_robot = username.startswith("robot$")

        is_admin = _coerce_bool(
            user.get("has_admin_role")
            or user.get("sysadmin_flag")
            or user.get("admin_role_in_auth")
        )

        return {
            "user_id": user_id,
            "username": username,
            "display_name": display_name,
            "email": email,
            "creation_time": creation_time,
            "update_time": update_time,
            "is_robot": is_robot,
            "is_admin": is_admin,
            "projects": projects,
            "project_roles": project_roles,
            "role_names": role_names,
        }


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False
