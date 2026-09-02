from typing import Mapping

from httpx import HTTPStatusError, RequestError
from port_ocean.context.ocean import ocean

from initialize_client import get_or_create_jira_client
from jira.probe.permissions import JiraKindPermissionVerdict
from kinds import Kinds
from port_ocean.core.probe import ProbeContext, ProbeCheck, ProbeCheckStatus


class JiraPermissionProbe:
    def __init__(self, context: ProbeContext) -> None:
        self.context = context
        self.permission_verdict = JiraKindPermissionVerdict()
        self.client = get_or_create_jira_client()

    async def run(self) -> None:
        permission_keys = _collect_required_permissions(
            [
                kind
                for kind in self.context.available_kinds
                if kind != Kinds.TEAM
            ],
            self.permission_verdict.kind_permissions,
        )

        try:
            permissions = await self.client.get_current_user_permissions(permission_keys)
        except (HTTPStatusError, RequestError):
            await self.context.fail(f"Failed to fetch user permissions.")
            return

        checks = await self.context.add_scopes({})
        await self._resolve_permission_checks(checks, permissions)
        team_check = next(
            (check for check in checks if check.kind == Kinds.TEAM),
            None,
        )
        if team_check is not None:
            await self._resolve_team_check(team_check)

    async def _resolve_permission_checks(
        self,
        checks: list[ProbeCheck],
        permissions: dict[str, bool],
    ) -> None:
        for check in checks:
            if check.kind == Kinds.TEAM:
                continue
            check.status, check.message = self.permission_verdict.verdict(
                check.kind,
                permissions,
            )
        await self.context.update_progress()

    async def _resolve_team_check(
        self,
        check: ProbeCheck,
    ) -> None:
        org_id = ocean.integration_config.get("atlassian_organization_id")
        if not org_id:
            check.status = ProbeCheckStatus.FAILURE
            check.message = "Atlassian organization ID is required to sync teams"
            await self.context.update_progress()
            return

        try:
            await self.client.verify_teams_access(org_id)
        except HTTPStatusError as error:
            check.status = ProbeCheckStatus.FAILURE
            check.message = (
                f"Jira returned HTTP {error.response.status_code} "
                "while verifying teams access"
            )
            await self.context.update_progress()
            return
        except RequestError as error:
            check.status = ProbeCheckStatus.FAILURE
            check.message = (
                "Jira could not be reached while verifying teams access: "
                f"{error}"
            )
            await self.context.update_progress()
            return

        check.status = ProbeCheckStatus.SUCCESS
        check.message = "Atlassian Teams API access verified"
        await self.context.update_progress()


def _collect_required_permissions(
    available_kinds: list[str],
    kind_permissions: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            permission
            for kind in available_kinds
            for permission in kind_permissions.get(kind, ())
        )
    )
