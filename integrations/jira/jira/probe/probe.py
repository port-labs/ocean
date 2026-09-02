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
        permission_keys = list({
            permission
            for kind in self.context.available_kinds
            for permission in self.permission_verdict.kind_permissions.get(kind, ())
        })

        try:
            await self.client.verify_current_user()
        except (HTTPStatusError, RequestError):
            await self.context.fail("Failed to verify Jira authentication.")
            return

        checks = await self.context.add_scopes({})

        try:
            permissions = await self.client.get_current_user_permissions(permission_keys)
        except HTTPStatusError as error:
            await self._fail_permission_checks(
                checks,
                (
                    f"Jira returned HTTP {error.response.status_code} "
                    "while fetching user permissions"
                ),
            )
        except RequestError as error:
            await self._fail_permission_checks(
                checks,
                (
                    "Jira could not be reached while fetching user permissions: "
                    f"{error}"
                ),
            )
        else:
            await self._resolve_permission_checks(checks, permissions)

        team_check = next(
            (check for check in checks if check.kind == Kinds.TEAM),
            None,
        )
        if team_check is not None:
            await self._resolve_team_check(team_check)

    async def _fail_permission_checks(
        self,
        checks: list[ProbeCheck],
        message: str,
    ) -> None:
        for check in checks:
            if check.kind == Kinds.TEAM:
                continue
            check.status = ProbeCheckStatus.FAILURE
            check.message = message
        await self.context.update_progress()

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
