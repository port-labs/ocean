from jira.overrides import JiraPortAppConfig
from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
)
from port_ocean.core.probe import KindPermissionVerdict, PermissionCombination


class JiraKindPermissionVerdict(KindPermissionVerdict):
    def load_kind_permissions(self) -> dict[str, tuple[str, ...]]:
        return get_kind_probe_permissions(JiraPortAppConfig)

    @property
    def combination(self) -> PermissionCombination:
        return PermissionCombination.AND

    def granted_message(self, granted: tuple[str, ...]) -> str:
        if granted == ("BROWSE_PROJECTS",):
            return "Basic Jira access verified"
        return super().granted_message(granted)
