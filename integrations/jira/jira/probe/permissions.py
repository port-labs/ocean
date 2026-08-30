from collections.abc import Sequence

import httpx

from port_ocean.core.probe import ProbeCheck, ProbeCheckStatus, ProbeContext
from port_ocean.exceptions.probe import ProbeFailedError

from initialize_client import get_or_create_jira_client

UNAUTHORIZED_STATUS_CODES = (
    httpx.codes.UNAUTHORIZED,
    httpx.codes.FORBIDDEN,
)

KIND_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "project": ("BROWSE_PROJECTS",),
    "issue": ("BROWSE_PROJECTS",),
    "user": ("USER_PICKER",),
    "release": ("BROWSE_PROJECTS",),
    "board": ("BROWSE_PROJECTS",),
    "sprint": ("BROWSE_PROJECTS",),
    "backlog": ("BROWSE_PROJECTS",),
    "epic": ("BROWSE_PROJECTS",),
    "worklog": ("BROWSE_PROJECTS",),
    "component": ("BROWSE_PROJECTS",),
}


class JiraPermissionProbe:
    def __init__(self, context: ProbeContext) -> None:
        self.context = context

    async def run(self) -> None:
        checks = self.context.add_scopes({})
        permission_keys = tuple(
            dict.fromkeys(
                permission
                for check in checks
                for permission in KIND_PERMISSIONS.get(check.kind, ())
            )
        )
        client = get_or_create_jira_client()
        try:
            permissions = await client.get_current_user_permissions(permission_keys)
        except (httpx.HTTPStatusError, httpx.RequestError) as error:
            raise ProbeFailedError(_lookup_failure_message(error)) from error

        self._resolve_checks(checks, permissions)

    def _resolve_checks(
        self,
        checks: Sequence[ProbeCheck],
        permissions: dict[str, bool],
    ) -> None:
        for check in checks:
            check.status, check.message = _permission_verdict(check.kind, permissions)
        self.context.update_progress()


def _lookup_failure_message(
    error: httpx.HTTPStatusError | httpx.RequestError,
) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        if status_code in UNAUTHORIZED_STATUS_CODES:
            return f"Jira rejected the configured credentials with HTTP {status_code}"
        return f"Jira returned HTTP {status_code} while reading the current user's permissions"

    return f"Jira could not be reached while reading the current user's permissions: {error}"


def _permission_verdict(
    kind: str,
    permissions: dict[str, bool],
) -> tuple[ProbeCheckStatus, str]:
    required = KIND_PERMISSIONS.get(kind)
    if required is None:
        return (
            ProbeCheckStatus.UNKNOWN,
            f"No Jira permission mapping is defined for {kind}",
        )

    missing = [permission for permission in required if permission not in permissions]
    if missing:
        return (
            ProbeCheckStatus.UNKNOWN,
            "Jira did not return permission information for " + ", ".join(missing),
        )

    denied = [permission for permission in required if not permissions[permission]]
    if denied:
        return (
            ProbeCheckStatus.FAILURE,
            "Jira requires " + ", ".join(denied),
        )

    return (
        ProbeCheckStatus.SUCCESS,
        "Jira grants " + ", ".join(required),
    )
