from collections.abc import Mapping

from integration import AWSPortAppConfig
from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
)
from port_ocean.core.probe import KindPermissionVerdict, PermissionCombination


class AwsKindPermissionVerdict(KindPermissionVerdict):
    def load_kind_permissions(self) -> Mapping[str, tuple[str, ...]]:
        return get_kind_probe_permissions(AWSPortAppConfig)

    @property
    def combination(self) -> PermissionCombination:
        return PermissionCombination.AND

    def is_granted(self, permission: str, permissions: Mapping[str, object]) -> bool:
        return str(permissions.get(permission, "")).lower() == "allowed"

    def missing_message(self, missing: tuple[str, ...]) -> str | None:
        return "IAM simulation did not return a decision for: " + ", ".join(missing)
