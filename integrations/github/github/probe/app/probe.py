from github.helpers.exceptions import AuthenticationException
from github.probe.app.permissions import AppKindPermissionVerdict
from port_ocean.core.probe import KindPermissionVerdict, ProbeCheckStatus

from github.probe.base_probe_flow import GitHubPermissionProbeFlow, org_scopes

MISSING_PERMISSIONS_MESSAGE = (
    "Your app installation token is valid, but permission verification is not "
    "available because GitHub did not return installation permissions."
)


class GitHubAppPermissionProbe(GitHubPermissionProbeFlow):
    @property
    def _permission_verdict_class(self) -> type[KindPermissionVerdict]:
        return AppKindPermissionVerdict

    async def _fail_org_checks(self, organization: str, message: str) -> None:
        checks = await self.context.add_scopes({"org": organization})
        for check in checks:
            check.status = ProbeCheckStatus.FAILURE
            check.message = message

        await self.context.update_progress()

    async def run(self) -> None:
        for authenticator in self.authenticators:
            if authenticator.organization is None:
                continue

            try:
                token = await authenticator.get_token()
            except AuthenticationException as error:
                await self._fail_org_checks(authenticator.organization, str(error))
                continue

            if token.permissions is None:
                await self._fail_org_checks(authenticator.organization, MISSING_PERMISSIONS_MESSAGE)
                continue

            checks = await self.context.add_scopes(
                *org_scopes(  # type: ignore[arg-type]
                    [
                        authenticator.organization
                        for authenticator in self.authenticators
                        if authenticator.organization is not None
                    ]
                )
            )

            await self._resolve_checks(checks, token.permissions or {})
