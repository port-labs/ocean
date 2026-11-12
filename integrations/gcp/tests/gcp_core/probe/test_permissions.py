from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
)


def test_verdict_loads_kind_probe_permissions() -> None:
    # Arrange
    from gcp_core.overrides import GCPPortAppConfig
    from gcp_core.probe.permissions import GcpKindPermissionVerdict

    verdict = GcpKindPermissionVerdict()

    # Act + Assert
    assert verdict.kind_permissions == get_kind_probe_permissions(GCPPortAppConfig)
    # gcpCloudFunction carries a per-mapping URL, so it has no permission to check
    assert "gcpCloudFunction" not in verdict.kind_permissions


def test_every_mapped_kind_belongs_to_exactly_one_container_level() -> None:
    # Arrange
    from gcp_core.overrides import GCPPortAppConfig
    from gcp_core.probe.probe import _LEVELS

    mapped_kinds = set(get_kind_probe_permissions(GCPPortAppConfig))
    level_kinds = [kind for level in _LEVELS for kind in level.kinds]

    # Act + Assert
    assert len(level_kinds) == len(set(level_kinds)), "a kind is claimed by two levels"
    assert set(level_kinds) == mapped_kinds, (
        "declare the kind's level in _LEVELS, or drop its probe_permissions: "
        f"unclaimed={sorted(mapped_kinds - set(level_kinds))} "
        f"unmapped={sorted(set(level_kinds) - mapped_kinds)}"
    )
