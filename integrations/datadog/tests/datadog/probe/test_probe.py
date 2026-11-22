from typing import Any
from unittest.mock import AsyncMock

import pytest
from port_ocean.core.probe import ProbeCheckStatus, ProbeContext, ProbeStatus

from datadog.exceptions import IntegrationMissingConfigError
from datadog.probe.probe import DatadogPermissionProbe
from tests.datadog.probe.conftest import (
    BASE_URL,
    USER_ID,
    application_key,
    http_status_error,
    make_client,
    request_error,
)


def statuses(context: ProbeContext) -> dict[str, ProbeCheckStatus]:
    return {check.kind: check.status for check in context.checks}


@pytest.mark.asyncio
async def test_resolves_kinds_from_owner_permissions_in_three_calls(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    client = make_client(role_permissions={"monitors_read", "apm_service_catalog_read"})
    set_clients([client])
    probe_context.available_kinds = ["monitor", "slo", "serviceMetric", "team"]

    await DatadogPermissionProbe(probe_context).run()

    client.get_current_user.assert_awaited_once()
    client.get_user_permissions.assert_awaited_once_with(USER_ID)
    client.get_current_user_application_keys.assert_awaited_once()
    client.validate_api_key.assert_not_awaited()
    assert statuses(probe_context) == {
        "monitor": ProbeCheckStatus.SUCCESS,
        "slo": ProbeCheckStatus.FAILURE,
        "serviceMetric": ProbeCheckStatus.FAILURE,
        # teams_read is scope-only: every unscoped key holds it
        "team": ProbeCheckStatus.SUCCESS,
    }
    slo_check = next(c for c in probe_context.checks if c.kind == "slo")
    assert slo_check.message is not None
    assert slo_check.message.startswith("Missing permission(s): slos_read.")
    metric_check = next(c for c in probe_context.checks if c.kind == "serviceMetric")
    assert metric_check.message is not None
    assert "timeseries_query" in metric_check.message


@pytest.mark.asyncio
async def test_scoped_key_limits_permissions_to_its_scopes(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    client = make_client(
        role_permissions={"monitors_read", "slos_read"},
        get_current_user_application_keys=AsyncMock(
            return_value=[
                application_key("zzzz", None),
                application_key("abcd", ["monitors_read"]),
            ]
        ),
    )
    set_clients([client])
    probe_context.available_kinds = ["monitor", "slo", "team"]

    await DatadogPermissionProbe(probe_context).run()

    assert statuses(probe_context) == {
        "monitor": ProbeCheckStatus.SUCCESS,
        "slo": ProbeCheckStatus.FAILURE,
        "team": ProbeCheckStatus.FAILURE,
    }


@pytest.mark.asyncio
async def test_unreadable_key_scopes_fall_back_to_role_permissions(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    client = make_client(
        role_permissions={"slos_read"},
        get_current_user_application_keys=AsyncMock(
            side_effect=http_status_error(403, "/api/v2/current_user/application_keys")
        ),
    )
    set_clients([client])
    probe_context.available_kinds = ["slo"]

    await DatadogPermissionProbe(probe_context).run()

    assert statuses(probe_context) == {"slo": ProbeCheckStatus.SUCCESS}


@pytest.mark.parametrize(
    "validate_error, expected_message",
    [
        (
            http_status_error(403, "/api/v1/validate"),
            "Failed to verify Datadog authentication. Ensure the API key is valid.",
        ),
        (
            None,
            "Failed to verify Datadog authentication. "
            "Ensure the application key is valid.",
        ),
    ],
)
@pytest.mark.asyncio
async def test_rejected_credentials_fail_probe_and_name_the_invalid_key(
    probe_context: ProbeContext,
    set_clients: Any,
    validate_error: Exception | None,
    expected_message: str,
) -> None:
    client = make_client(
        get_current_user=AsyncMock(side_effect=http_status_error(401)),
        validate_api_key=AsyncMock(side_effect=validate_error),
    )
    set_clients([client])
    probe_context.available_kinds = ["monitor"]

    await DatadogPermissionProbe(probe_context).run()

    assert probe_context.status is ProbeStatus.FAILED
    assert probe_context.message == expected_message
    assert probe_context.checks == []
    client.get_user_permissions.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrong_base_url_fails_probe(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    client = make_client(get_current_user=AsyncMock(side_effect=http_status_error(404)))
    set_clients([client])
    probe_context.available_kinds = ["monitor"]

    await DatadogPermissionProbe(probe_context).run()

    assert probe_context.status is ProbeStatus.FAILED
    assert probe_context.message == (
        "Could not find the Datadog API at the configured base URL, "
        "please ensure the Datadog base URL matches your Datadog site."
    )
    client.validate_api_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_unreachable_datadog_fails_probe(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    set_clients([make_client(get_current_user=AsyncMock(side_effect=request_error()))])
    probe_context.available_kinds = ["monitor"]

    await DatadogPermissionProbe(probe_context).run()

    assert probe_context.status is ProbeStatus.FAILED
    assert probe_context.message is not None
    assert probe_context.message.startswith(
        "Datadog could not be reached while verifying authentication"
    )


@pytest.mark.asyncio
async def test_oauth_token_skips_key_scopes_and_validation(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    client = make_client(access_token="token", role_permissions={"hosts_read"})
    set_clients([client])
    probe_context.available_kinds = ["host"]

    await DatadogPermissionProbe(probe_context).run()

    client.get_current_user_application_keys.assert_not_awaited()
    assert statuses(probe_context) == {"host": ProbeCheckStatus.SUCCESS}


@pytest.mark.asyncio
async def test_failed_permission_lookup_fails_every_check(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    client = make_client(
        get_user_permissions=AsyncMock(
            side_effect=http_status_error(403, f"/api/v2/users/{USER_ID}/permissions")
        )
    )
    set_clients([client])
    probe_context.available_kinds = ["monitor", "team"]

    await DatadogPermissionProbe(probe_context).run()

    assert statuses(probe_context) == {
        "monitor": ProbeCheckStatus.FAILURE,
        "team": ProbeCheckStatus.FAILURE,
    }
    assert probe_context.checks[0].message == (
        "Datadog returned HTTP 403 while reading the permissions of the "
        "application key's owner. If the application key is scoped, add the "
        "user_access_read scope to it."
    )


@pytest.mark.asyncio
async def test_multi_org_reports_checks_per_org_and_isolates_bad_credentials(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    good = make_client(
        org_name="prod", org_id="abc", role_permissions={"monitors_read"}
    )
    bad = make_client(
        org_id="def", get_current_user=AsyncMock(side_effect=http_status_error(403))
    )
    unnamed = make_client()
    set_clients([good, bad, unnamed], multi_org=True)
    probe_context.available_kinds = ["monitor"]

    await DatadogPermissionProbe(probe_context).run()

    results = {
        check.scopes["org"]: (check.status, check.message)
        for check in probe_context.checks
    }
    assert results == {
        "prod": (ProbeCheckStatus.SUCCESS, "Datadog access verified: monitors_read"),
        "def": (
            ProbeCheckStatus.FAILURE,
            "Failed to verify Datadog authentication. "
            "Ensure the application key is valid.",
        ),
        f"#3 ({BASE_URL})": (
            ProbeCheckStatus.FAILURE,
            "Missing permission(s): monitors_read. Grant them to the role of the "
            "application key's owner, and to the key's scopes if it is scoped.",
        ),
    }
    bad.get_user_permissions.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_credential_map_fails_probe(
    probe_context: ProbeContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    def raise_missing() -> None:
        raise IntegrationMissingConfigError("Invalid datadogCredentialMap")

    monkeypatch.setattr("datadog.probe.probe.get_client_manager", raise_missing)
    probe_context.available_kinds = ["monitor"]

    await DatadogPermissionProbe(probe_context).run()

    assert probe_context.status is ProbeStatus.FAILED
    assert probe_context.message == "Invalid datadogCredentialMap"
