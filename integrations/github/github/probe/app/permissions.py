from typing import Mapping

from github.probe.app.probe import _PERMISSION_LEVELS
from integration import GithubPortAppConfig
from port_ocean.core.handlers.port_app_config.validators import get_kind_probe_permissions
from port_ocean.core.probe import KindPermissionVerdict, PermissionCombination


class AppKindPermissionVerdict(KindPermissionVerdict):
    def load_kind_permissions(self) -> Mapping[str, tuple[str, ...]]:
        return get_kind_probe_permissions(GithubPortAppConfig, permission_key="app")

    @property
    def combination(self) -> PermissionCombination:
        return PermissionCombination.OR

    def is_granted(self, permission: str, permissions: Mapping[str, object]) -> bool:
        level = permissions.get(permission, "")
        if not isinstance(level, str):
            return False
        return _PERMISSION_LEVELS.get(level, 0) >= _PERMISSION_LEVELS["read"]
