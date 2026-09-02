from github.helpers.exceptions import AuthenticationException
from github.probe.app.permissions import AppKindPermissionVerdict
from port_ocean.core.probe import KindPermissionVerdict

from github.probe.base_probe_flow import GitHubPermissionProbeFlow, org_scopes


MISSING_PERMISSIONS_MESSAGE = (
    "Your app installation token is valid, but permission verification is not "
    "available because GitHub did not return installation permissions."
)


class GitHubAppPermissionProbe(GitHubPermissionProbeFlow):
    def _permission_verdict_class(self) -> type[KindPermissionVerdict]:
        return AppKindPermissionVerdict

    async def run(self) -> None:
        try:
            tokens = [
                await authenticator.get_token()
                for authenticator in self.authenticators
            ]
        except AuthenticationException as error:
            await self.context.fail(str(error))
            return

        if any(token.permissions is None for token in tokens):
            self.context.message = MISSING_PERMISSIONS_MESSAGE
            return

        checks = await self.context.add_scopes(
            *org_scopes(
                [authenticator.organization for authenticator in self.authenticators]
            )
        )
        kind_count = len(self.context.available_kinds)
        for index, token in enumerate(tokens):
            pending = checks[index * kind_count : (index + 1) * kind_count]
            await self._resolve_checks(pending, token.permissions or {})
