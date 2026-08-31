from collections.abc import Mapping

from port_ocean.core.handlers.port_app_config.validators import get_kind_probe_permissions
from port_ocean.core.probe import KindPermissionVerdict, PermissionCombination

from github.probe.permissions.base import GitHubPermissionProbeFlow, org_scopes
from integration import GithubPortAppConfig

_PERMISSION_LEVELS = {"read": 1, "write": 2, "admin": 3}

MISSING_APP_PERMISSIONS_MESSAGE = (
    "GitHub did not return permissions for the installation token"
)


class AppKindPermissionVerdict(KindPermissionVerdict):
    def load_kind_permissions(self) -> Mapping[str, tuple[str, ...]]:
        return get_kind_probe_permissions(GithubPortAppConfig, permission_key="app")

    @property
    def combination(self) -> PermissionCombination:
        return PermissionCombination.OR

    def unmapped_message(self, kind: str) -> str:
        return f"No GitHub App permission mapping is defined for {kind}"

    def granted_message(self, granted: tuple[str, ...]) -> str:
        if len(granted) == 1:
            return f"GitHub App grants {granted[0]}"
        return "GitHub App grants " + ", ".join(granted)

    def denied_message(self, denied: tuple[str, ...]) -> str:
        if len(denied) == 1:
            return f"GitHub App requires read access for {denied[0]}"
        return "GitHub App requires read access for " + " or ".join(denied)

    def is_granted(self, permission: str, permissions: Mapping[str, object]) -> bool:
        level = permissions.get(permission, "")
        if not isinstance(level, str):
            return False
        return _PERMISSION_LEVELS.get(level, 0) >= _PERMISSION_LEVELS["read"]


_APP_KIND_PERMISSION_VERDICT = AppKindPermissionVerdict()


class GitHubAppPermissionProbe(GitHubPermissionProbeFlow):
    async def run(self) -> None:
        tokens = [
            await authenticator.get_token() for authenticator in self.authenticators
        ]
        for token in tokens:
            if token.permissions is None:
                self.context.fail(MISSING_APP_PERMISSIONS_MESSAGE)
                return

        pending = self.context.add_scopes(
            *org_scopes(
                [authenticator.organization for authenticator in self.authenticators]
            )
        )
        kind_count = len(self.context.available_kinds)
        for index, token in enumerate(tokens):
            checks = pending[index * kind_count : (index + 1) * kind_count]
            self._resolve_checks(
                checks,
                token.permissions,
                _APP_KIND_PERMISSION_VERDICT,
            )
