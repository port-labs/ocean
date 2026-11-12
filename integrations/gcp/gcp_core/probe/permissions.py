from collections.abc import Mapping

from gcp_core.overrides import GCPPortAppConfig
from gcp_core.utils import AssetTypesWithSpecialHandling
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

    def unmapped_message(self, kind: str) -> str:
        if kind == AssetTypesWithSpecialHandling.CLOUD_FUNCTION:
            return "Access to the configured function URL is not verified by the probe."
        return super().unmapped_message(kind)
