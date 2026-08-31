from collections.abc import Sequence

import httpx

from kinds import Kinds
from jira.overrides import JiraPortAppConfig
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.validators import get_kind_probe_permissions
from port_ocean.core.probe import (
    KindPermissionVerdict,
    PermissionCombination,
    ProbeCheck,
    ProbeCheckStatus,
    ProbeContext,
)

from initialize_client import get_or_create_jira_client
from jira.client import JiraClient

UNAUTHORIZED_STATUS_CODES = (
    httpx.codes.UNAUTHORIZED,
    httpx.codes.FORBIDDEN,
)


TEAM_ORG_ID_MISSING_MESSAGE = (
    "Atlassian organization ID is required to sync teams; "
    "configure atlassianOrganizationId in the integration settings"
)
TEAM_ACCESS_SUCCESS_MESSAGE = "Atlassian Teams API access verified"


class JiraKindPermissionVerdict(KindPermissionVerdict):
    def load_kind_permissions(self) -> dict[str, tuple[str, ...]]:
        return get_kind_probe_permissions(JiraPortAppConfig)

    @property
    def combination(self) -> PermissionCombination:
        return PermissionCombination.AND

    def unmapped_message(self, kind: str) -> str:
        return f"No Jira permission mapping is defined for {kind}"

    def missing_message(self, missing: tuple[str, ...]) -> str:
        return "Jira did not return permission information for " + ", ".join(missing)

    def granted_message(self, granted: tuple[str, ...]) -> str:
        return "Jira grants " + ", ".join(granted)

    def denied_message(self, denied: tuple[str, ...]) -> str:
        return "Jira requires " + ", ".join(denied)


_JIRA_KIND_PERMISSION_VERDICT = JiraKindPermissionVerdict()


class JiraPermissionProbe:
    def __init__(self, context: ProbeContext) -> None:
        self.context = context

    async def run(self) -> None:
        permission_keys = _collect_required_permissions(
            [
                kind
                for kind in self.context.available_kinds
                if kind != Kinds.TEAM
            ],
            _JIRA_KIND_PERMISSION_VERDICT.kind_permissions,
        )
        client = get_or_create_jira_client()
        try:
            permissions = await client.get_current_user_permissions(permission_keys)
        except (httpx.HTTPStatusError, httpx.RequestError) as error:
            self.context.fail(_lookup_failure_message(error))
            return

        checks = self.context.add_scopes({})
        self._resolve_permission_checks(checks, permissions)
        team_check = next(
            (check for check in checks if check.kind == Kinds.TEAM),
            None,
        )
        if team_check is not None:
            await self._resolve_team_check(team_check, client)

    def _resolve_permission_checks(
        self,
        checks: Sequence[ProbeCheck],
        permissions: dict[str, bool],
    ) -> None:
        for check in checks:
            if check.kind == Kinds.TEAM:
                continue
            check.status, check.message = _JIRA_KIND_PERMISSION_VERDICT.verdict(
                check.kind,
                permissions,
            )
        self.context.update_progress()

    async def _resolve_team_check(
        self,
        check: ProbeCheck,
        client: JiraClient,
    ) -> None:
        org_id = ocean.integration_config.get("atlassian_organization_id")
        if not org_id:
            check.status = ProbeCheckStatus.FAILURE
            check.message = TEAM_ORG_ID_MISSING_MESSAGE
            self.context.update_progress()
            return

        try:
            await client.verify_teams_access(org_id)
        except httpx.HTTPStatusError as error:
            check.status = ProbeCheckStatus.FAILURE
            check.message = (
                f"Jira returned HTTP {error.response.status_code} "
                "while verifying teams access"
            )
            self.context.update_progress()
            return
        except httpx.RequestError as error:
            check.status = ProbeCheckStatus.FAILURE
            check.message = (
                "Jira could not be reached while verifying teams access: "
                f"{error}"
            )
            self.context.update_progress()
            return

        check.status = ProbeCheckStatus.SUCCESS
        check.message = TEAM_ACCESS_SUCCESS_MESSAGE
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


def _collect_required_permissions(
    available_kinds: Sequence[str],
    kind_permissions: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            permission
            for kind in available_kinds
            for permission in kind_permissions.get(kind, ())
        )
    )
