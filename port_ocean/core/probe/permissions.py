from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import StrEnum

from port_ocean.core.probe.models import ProbeCheckStatus


class PermissionCombination(StrEnum):
    AND = "and"
    OR = "or"


class KindPermissionVerdict(ABC):
    @property
    @abstractmethod
    def kind_permissions(self) -> Mapping[str, tuple[str, ...]]:
        """Maps probe kinds to the permissions required to sync them."""

    @property
    @abstractmethod
    def combination(self) -> PermissionCombination:
        """Whether all mapped permissions must be granted (AND) or any one (OR)."""

    @abstractmethod
    def unmapped_message(self, kind: str) -> str:
        """Message when no permission mapping exists for a kind."""

    @abstractmethod
    def granted_message(self, granted: tuple[str, ...]) -> str:
        """Message when the required permissions are satisfied."""

    @abstractmethod
    def denied_message(self, denied: tuple[str, ...]) -> str:
        """Message when the required permissions are not satisfied."""

    def missing_message(self, missing: tuple[str, ...]) -> str | None:
        """Message when the provider omitted one or more required permissions."""
        return None

    def is_granted(self, permission: str, permissions: Mapping[str, object]) -> bool:
        return permission in permissions and bool(permissions[permission])

    def verdict(
        self,
        kind: str,
        permissions: Mapping[str, object],
    ) -> tuple[ProbeCheckStatus, str]:
        required = self.kind_permissions.get(kind)
        if required is None:
            return ProbeCheckStatus.UNKNOWN, self.unmapped_message(kind)

        if self.combination is PermissionCombination.AND:
            missing = [
                permission for permission in required if permission not in permissions
            ]
            missing_message = self.missing_message(tuple(missing)) if missing else None
            if missing_message is not None:
                return ProbeCheckStatus.UNKNOWN, missing_message

            denied = tuple(
                permission
                for permission in required
                if not self.is_granted(permission, permissions)
            )
            if denied:
                return ProbeCheckStatus.FAILURE, self.denied_message(denied)

            return ProbeCheckStatus.SUCCESS, self.granted_message(required)

        granted = tuple(
            permission
            for permission in required
            if self.is_granted(permission, permissions)
        )
        if granted:
            return ProbeCheckStatus.SUCCESS, self.granted_message(granted)

        return ProbeCheckStatus.FAILURE, self.denied_message(required)
