from github.probe.app.permissions import AppKindPermissionVerdict
from port_ocean.core.probe import KindPermissionVerdict

from github.probe.base_probe_flow import GitHubPermissionProbeFlow, org_scopes


class GitHubAppPermissionProbe(GitHubPermissionProbeFlow):
    def _permission_verdict_class(self) -> type[KindPermissionVerdict]:
        return AppKindPermissionVerdict

    async def run(self) -> None:
        tokens = [
            await authenticator.get_token() for authenticator in self.authenticators
        ]
        for token in tokens:
            if token.permissions is None:
                await self.context.fail("GitHub did not return permissions for the installation token")
                return

        pending = await self.context.add_scopes(
            *org_scopes(
                [authenticator.organization for authenticator in self.authenticators]
            )
        )
        kind_count = len(self.context.available_kinds)
        for index, token in enumerate(tokens):
            checks = pending[index * kind_count : (index + 1) * kind_count]
            await self._resolve_checks(
                checks,
                token.permissions,
            )
