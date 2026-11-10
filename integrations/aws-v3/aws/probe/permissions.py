from collections.abc import Mapping

from aws_integration.overrides import AWSPortAppConfig
from port_ocean.core.handlers.port_app_config.models import CUSTOM_KIND
from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
)
from port_ocean.core.probe import (
    KindPermissionVerdict,
    PermissionCombination,
    ProbeCheckStatus,
)

CUSTOM_KIND_UNVERIFIED_NOTE = (
    ". Service permissions required by each configured Cloud Control type "
    "are not verified."
)


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

    def verdict(
        self,
        kind: str,
        permissions: Mapping[str, object],
    ) -> tuple[ProbeCheckStatus, str]:
        status, message = super().verdict(kind, permissions)
        if kind == CUSTOM_KIND and status is ProbeCheckStatus.SUCCESS:
            message += CUSTOM_KIND_UNVERIFIED_NOTE
        return status, message
