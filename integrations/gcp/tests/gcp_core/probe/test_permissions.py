from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
    get_port_app_config_kinds,
)

# gcpCloudFunction carries a per-mapping URL, so there is no permission to check
UNPROBED_KINDS = {"gcpCloudFunction"}


def test_verdict_loads_kind_probe_permissions() -> None:
    # Arrange
    from gcp_core.overrides import GCPPortAppConfig
    from gcp_core.probe.permissions import GcpKindPermissionVerdict

    verdict = GcpKindPermissionVerdict()

    # Act + Assert
    assert verdict.kind_permissions == get_kind_probe_permissions(GCPPortAppConfig)


def test_every_kind_is_probed_or_deliberately_exempt() -> None:
    # Arrange
    from gcp_core.overrides import GCPPortAppConfig

    kinds = set(get_port_app_config_kinds(GCPPortAppConfig))
    mapped = set(get_kind_probe_permissions(GCPPortAppConfig))

    # Act + Assert
    assert kinds - mapped == UNPROBED_KINDS, (
        "a kind reaches test connection with no verdict: "
        f"give it probe_permissions or list it in UNPROBED_KINDS: "
        f"{sorted(kinds - mapped - UNPROBED_KINDS)}"
    )


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


def test_no_kind_mixes_its_levels_implied_permission_with_another() -> None:
    # Arrange
    from gcp_core.overrides import GCPPortAppConfig
    from gcp_core.probe.probe import _LEVELS

    permissions = get_kind_probe_permissions(GCPPortAppConfig)

    # Act + Assert
    for level in _LEVELS:
        for kind in level.kinds:
            required = set(permissions[kind])
            assert required == {level.implied_permission} or (
                level.implied_permission not in required
            ), f"{kind} needs {level.implied_permission} alongside {sorted(required)}"
