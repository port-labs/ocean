from typing import Mapping

from integration import GithubPortAppConfig
from port_ocean.core.handlers.port_app_config.validators import get_kind_probe_permissions
from port_ocean.core.probe import KindPermissionVerdict, PermissionCombination


class PatKindPermissionVerdict(KindPermissionVerdict):
    def load_kind_permissions(self) -> Mapping[str, tuple[str, ...]]:
        return get_kind_probe_permissions(GithubPortAppConfig, permission_key="pat")

    @property
    def combination(self) -> PermissionCombination:
        return PermissionCombination.OR
