from collections.abc import Mapping

import pytest

from port_ocean.core.probe.models import ProbeCheckStatus
from port_ocean.core.probe.permissions import (
    KindPermissionVerdict,
    PermissionCombination,
)

KIND_PERMISSIONS = {
    "project": ("BROWSE_PROJECTS",),
    "user": ("USER_PICKER",),
    "package": ("organization_packages", "packages"),
}


class AndKindPermissionVerdict(KindPermissionVerdict):
    def load_kind_permissions(self) -> dict[str, tuple[str, ...]]:
        return KIND_PERMISSIONS

    @property
    def combination(self) -> PermissionCombination:
        return PermissionCombination.AND

    def unmapped_message(self, kind: str) -> str:
        return "unmapped"

    def missing_message(self, missing: tuple[str, ...]) -> str:
        return f"missing {', '.join(missing)}"

    def granted_message(self, granted: tuple[str, ...]) -> str:
        return f"grants {', '.join(granted)}"

    def denied_message(self, denied: tuple[str, ...]) -> str:
        return f"requires {', '.join(denied)}"


class OrKindPermissionVerdict(KindPermissionVerdict):
    def load_kind_permissions(self) -> dict[str, tuple[str, ...]]:
        return KIND_PERMISSIONS

    @property
    def combination(self) -> PermissionCombination:
        return PermissionCombination.OR

    def unmapped_message(self, kind: str) -> str:
        return "unmapped"

    def granted_message(self, granted: tuple[str, ...]) -> str:
        return f"grants {', '.join(granted)}"

    def denied_message(self, denied: tuple[str, ...]) -> str:
        return f"requires {' or '.join(denied)}"


class PresenceOrKindPermissionVerdict(OrKindPermissionVerdict):
    def load_kind_permissions(self) -> dict[str, tuple[str, ...]]:
        return {"project": ("repo",)}

    def is_granted(self, permission: str, permissions: Mapping[str, object]) -> bool:
        return permission in permissions


@pytest.mark.parametrize(
    "permissions, expected_status, expected_message",
    [
        (
            {"BROWSE_PROJECTS": True},
            ProbeCheckStatus.SUCCESS,
            "grants BROWSE_PROJECTS",
        ),
        (
            {},
            ProbeCheckStatus.UNKNOWN,
            "missing BROWSE_PROJECTS",
        ),
        (
            {"BROWSE_PROJECTS": False},
            ProbeCheckStatus.FAILURE,
            "requires BROWSE_PROJECTS",
        ),
    ],
)
def test_and_combination_requires_all_permissions(
    permissions: dict[str, bool],
    expected_status: ProbeCheckStatus,
    expected_message: str,
) -> None:
    status, message = AndKindPermissionVerdict().verdict("project", permissions)

    assert status is expected_status
    assert expected_message in message


def test_or_combination_accepts_any_required_permission() -> None:
    status, message = OrKindPermissionVerdict().verdict(
        "package",
        {"packages": True},
    )

    assert status is ProbeCheckStatus.SUCCESS
    assert message == "grants packages"


def test_or_combination_fails_when_no_required_permission_is_granted() -> None:
    status, message = OrKindPermissionVerdict().verdict(
        "package",
        {"metadata": True},
    )

    assert status is ProbeCheckStatus.FAILURE
    assert message == "requires organization_packages or packages"


def test_custom_is_granted_supports_presence_checks() -> None:
    status, message = PresenceOrKindPermissionVerdict().verdict(
        "project",
        {"repo": True},
    )

    assert status is ProbeCheckStatus.SUCCESS
    assert message == "grants repo"
