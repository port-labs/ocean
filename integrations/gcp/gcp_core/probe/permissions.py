from collections.abc import Mapping

from gcp_core.overrides import GCPPortAppConfig
from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
)
from port_ocean.core.probe import KindPermissionVerdict, PermissionCombination


class GcpKindPermissionVerdict(KindPermissionVerdict):
    def load_kind_permissions(self) -> Mapping[str, tuple[str, ...]]:
        return get_kind_probe_permissions(GCPPortAppConfig)

    @property
    def combination(self) -> PermissionCombination:
        return PermissionCombination.AND
