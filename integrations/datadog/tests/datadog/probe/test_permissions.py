from port_ocean.core.handlers.port_app_config.validators import (
    get_port_app_config_kinds,
)
from port_ocean.core.probe import ProbeCheckStatus

from datadog.overrides import DataDogPortAppConfig
from datadog.probe.permissions import DatadogKindPermissionVerdict


def test_every_supported_kind_declares_probe_permissions() -> None:
    verdict = DatadogKindPermissionVerdict()

    assert set(verdict.kind_permissions) == set(
        get_port_app_config_kinds(DataDogPortAppConfig)
    )


def test_kind_needs_all_of_its_permissions() -> None:
    verdict = DatadogKindPermissionVerdict()

    status, message = verdict.verdict("serviceMetric", {"timeseries_query": True})

    assert status is ProbeCheckStatus.FAILURE
    assert message.startswith("Missing permission(s): apm_service_catalog_read.")


def test_granted_kind_lists_its_permissions() -> None:
    verdict = DatadogKindPermissionVerdict()

    status, message = verdict.verdict(
        "serviceMetric",
        {"apm_service_catalog_read": True, "timeseries_query": True},
    )

    assert status is ProbeCheckStatus.SUCCESS
    assert message == (
        "Datadog access verified: apm_service_catalog_read, timeseries_query"
    )
