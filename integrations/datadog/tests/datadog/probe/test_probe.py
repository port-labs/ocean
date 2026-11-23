import asyncio
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from port_ocean.core.probe import ProbeCheckStatus, ProbeContext, ProbeStatus

from datadog.client import DatadogClient
from datadog.exceptions import IntegrationMissingConfigError
from datadog.probe.probe import DatadogPermissionProbe
from tests.datadog.probe.conftest import (
    BASE_URL,
    USER_ID,
    application_key,
    current_user,
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
    assert probe_context.message is None
    assert statuses(probe_context) == {
        "monitor": ProbeCheckStatus.SUCCESS,
        "slo": ProbeCheckStatus.FAILURE,
        "serviceMetric": ProbeCheckStatus.FAILURE,
        # teams_read is scope-only: every unscoped key holds it
        "team": ProbeCheckStatus.SUCCESS,
    }
    slo_check = next(c for c in probe_context.checks if c.kind == "slo")
    assert slo_check.message is not None
    assert slo_check.message == "Missing permission(s): slos_read"
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
async def test_unreadable_key_scopes_mark_role_grants_unknown(
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

    [check] = probe_context.checks
    assert check.status is ProbeCheckStatus.UNKNOWN
    assert check.message == (
        "The owner's role grants slos_read, but the application key's scopes "
        "could not be read to confirm it."
    )
    assert probe_context.message is None


@pytest.mark.asyncio
async def test_unreadable_key_scopes_keep_role_denials_as_failures(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    client = make_client(
        get_current_user_application_keys=AsyncMock(return_value=[]),
    )
    set_clients([client])
    probe_context.available_kinds = ["slo"]

    await DatadogPermissionProbe(probe_context).run()

    [check] = probe_context.checks
    assert check.status is ProbeCheckStatus.FAILURE
    assert check.message == "Missing permission(s): slos_read"


@pytest.mark.parametrize(
    "validate_error, expected_message",
    [
        (
            http_status_error(403, "/api/v1/validate"),
            "Failed to verify Datadog authentication. Ensure the API key is valid "
            "and the Datadog base URL matches your Datadog site.",
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
    assert probe_context.message is None


@pytest.mark.asyncio
async def test_unreadable_permissions_mark_every_check_unknown(
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
        "monitor": ProbeCheckStatus.UNKNOWN,
        "team": ProbeCheckStatus.UNKNOWN,
    }
    assert probe_context.status is not ProbeStatus.FAILED
    assert probe_context.checks[0].message == (
        "Datadog returned HTTP 403 while fetching user permissions. "
        "Required scope(s): user_access_read."
    )


@pytest.mark.asyncio
async def test_multi_org_reports_checks_per_org_and_isolates_bad_credentials(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    good = make_client(
        role_permissions={"monitors_read"},
        get_current_user=AsyncMock(return_value=current_user("prod", "abc")),
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
        "prod (abc)": (
            ProbeCheckStatus.SUCCESS,
            "Datadog access verified: monitors_read",
        ),
        "def": (
            ProbeCheckStatus.FAILURE,
            "Failed to verify Datadog authentication. "
            "Ensure the application key is valid.",
        ),
        f"{BASE_URL} (#3)": (
            ProbeCheckStatus.FAILURE,
            "Missing permission(s): monitors_read",
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


@pytest.mark.asyncio
async def test_effective_permissions_keep_only_those_selected_kinds_need(
    probe_context: ProbeContext,
) -> None:
    client = make_client(role_permissions={"monitors_read", "slos_read", "hosts_read"})

    probe = DatadogPermissionProbe(probe_context)
    permissions, scopes_verified = await probe._effective_permissions(
        cast(DatadogClient, client),
        USER_ID,
        {"monitors_read", "teams_read", "apm_read"},
    )

    assert permissions == {"monitors_read": True, "teams_read": True}
    assert scopes_verified


@pytest.mark.asyncio
async def test_single_org_checks_are_scoped_by_the_org_datadog_reports(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    set_clients(
        [
            make_client(
                role_permissions={"monitors_read"},
                get_current_user=AsyncMock(
                    return_value=current_user("mashevich", "pub-1")
                ),
            )
        ]
    )
    probe_context.available_kinds = ["monitor", "slo"]

    await DatadogPermissionProbe(probe_context).run()

    assert [check.scopes for check in probe_context.checks] == [
        {"org": "mashevich (pub-1)"},
        {"org": "mashevich (pub-1)"},
    ]


@pytest.mark.asyncio
async def test_org_scope_falls_back_to_a_unique_configured_label(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    set_clients(
        [
            make_client(org_name="prod", org_id="abc"),
            make_client(org_name="prod", org_id="xyz"),
            make_client(org_name="prod"),
            make_client(org_name="prod"),
            make_client(),
        ],
        multi_org=True,
    )
    probe_context.available_kinds = ["monitor"]

    await DatadogPermissionProbe(probe_context).run()

    assert [check.scopes["org"] for check in probe_context.checks] == [
        "prod (abc)",
        "prod (xyz)",
        "prod (#3)",
        "prod (#4)",
        f"{BASE_URL} (#5)",
    ]


@pytest.mark.asyncio
async def test_org_reported_by_datadog_takes_precedence_over_configuration(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    set_clients(
        [
            make_client(
                org_name="old name",
                org_id="abc",
                get_current_user=AsyncMock(return_value=current_user("prod", "abc")),
            ),
            make_client(
                get_current_user=AsyncMock(return_value=current_user("eu", "xyz"))
            ),
        ],
        multi_org=True,
    )
    probe_context.available_kinds = ["monitor"]

    await DatadogPermissionProbe(probe_context).run()

    assert [check.scopes["org"] for check in probe_context.checks] == [
        "prod (abc)",
        "eu (xyz)",
    ]


@pytest.mark.asyncio
async def test_unreadable_key_scopes_affect_only_that_orgs_checks(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    set_clients(
        [
            make_client(
                role_permissions={"monitors_read"},
                get_current_user=AsyncMock(return_value=current_user("prod", "abc")),
            ),
            make_client(
                role_permissions={"monitors_read"},
                get_current_user=AsyncMock(return_value=current_user("eu", "xyz")),
                get_current_user_application_keys=AsyncMock(return_value=[]),
            ),
        ],
        multi_org=True,
    )
    probe_context.available_kinds = ["monitor"]

    await DatadogPermissionProbe(probe_context).run()

    assert {check.scopes["org"]: check.status for check in probe_context.checks} == {
        "prod (abc)": ProbeCheckStatus.SUCCESS,
        "eu (xyz)": ProbeCheckStatus.UNKNOWN,
    }


@pytest.mark.asyncio
async def test_failed_probe_keeps_its_failure_message(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    set_clients(
        [
            make_client(
                access_token="token",
                get_current_user=AsyncMock(side_effect=http_status_error(401)),
            )
        ]
    )
    probe_context.available_kinds = ["monitor"]

    await DatadogPermissionProbe(probe_context).run()

    assert probe_context.status is ProbeStatus.FAILED
    assert probe_context.message == (
        "Failed to verify Datadog authentication. "
        "Ensure the Datadog access token is valid and the Datadog base URL "
        "matches your Datadog site."
    )


@pytest.mark.asyncio
async def test_empty_credential_map_fails_probe(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    set_clients([], multi_org=True)
    probe_context.available_kinds = ["monitor"]

    await DatadogPermissionProbe(probe_context).run()

    assert probe_context.status is ProbeStatus.FAILED
    assert probe_context.message == "No Datadog organizations were accessible."
    assert probe_context.checks == []


@pytest.mark.asyncio
async def test_orgs_are_probed_concurrently(
    probe_context: ProbeContext, set_clients: Any
) -> None:
    """Both orgs must be authenticating at once, or the first never finishes."""
    both_started = asyncio.Event()
    started = 0

    def authenticate_as(org_name: str, public_id: str) -> AsyncMock:
        async def get_current_user() -> dict[str, Any]:
            nonlocal started
            started += 1
            if started == 2:
                both_started.set()
            await both_started.wait()
            return current_user(org_name, public_id)

        return AsyncMock(side_effect=get_current_user)

    set_clients(
        [
            make_client(
                role_permissions={"monitors_read"},
                get_current_user=authenticate_as("prod", "abc"),
            ),
            make_client(
                role_permissions={"monitors_read"},
                get_current_user=authenticate_as("eu", "xyz"),
            ),
        ],
        multi_org=True,
    )
    probe_context.available_kinds = ["monitor"]

    await asyncio.wait_for(DatadogPermissionProbe(probe_context).run(), timeout=1)

    assert {check.scopes["org"]: check.status for check in probe_context.checks} == {
        "prod (abc)": ProbeCheckStatus.SUCCESS,
        "eu (xyz)": ProbeCheckStatus.SUCCESS,
    }
