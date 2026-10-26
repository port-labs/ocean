from unittest.mock import AsyncMock

import pytest

from plain.exceptions import PlainGraphQLError
from plain.probe.probe import PlainPermissionProbe
from port_ocean.core.probe import ProbeCheckStatus, ProbeContext, ProbeStatus
from tests.probe.conftest import (
    MockPlainProbe,
    plain_http_error,
    plain_unauthenticated_error,
    request_error,
)


@pytest.mark.asyncio
async def test_probe_resolves_permission_checks_for_available_kinds(
    mock_plain_probe: MockPlainProbe,
    probe_context: ProbeContext,
) -> None:
    mock_plain_probe.configure_client(
        get_my_permissions=AsyncMock(
            return_value={
                "company:read": True,
                "user:read": True,
            }
        ),
    )
    probe_context.available_kinds = ["company", "user"]

    await PlainPermissionProbe(probe_context).run()

    client = mock_plain_probe.client
    client.verify_authentication.assert_awaited_once()
    client.get_my_permissions.assert_awaited_once()
    assert [check.kind for check in probe_context.checks] == ["company", "user"]
    assert probe_context.checks[0].status is ProbeCheckStatus.SUCCESS
    assert probe_context.checks[1].status is ProbeCheckStatus.FAILURE
    assert probe_context.checks[1].message == "Missing permission(s): roles:read"


@pytest.mark.asyncio
async def test_probe_fails_when_authentication_returns_401(
    mock_plain_probe: MockPlainProbe,
    probe_context: ProbeContext,
) -> None:
    client = mock_plain_probe.configure_client(
        verify_authentication=AsyncMock(side_effect=plain_http_error(401)),
    )
    probe_context.available_kinds = ["company"]

    await PlainPermissionProbe(probe_context).run()

    assert probe_context.status is ProbeStatus.FAILED
    assert "Failed to verify Plain authentication" in (probe_context.message or "")
    assert probe_context.checks == []
    client.get_my_permissions.assert_not_called()


@pytest.mark.asyncio
async def test_probe_fails_when_authentication_is_unauthenticated_graphql(
    mock_plain_probe: MockPlainProbe,
    probe_context: ProbeContext,
) -> None:
    client = mock_plain_probe.configure_client(
        verify_authentication=AsyncMock(side_effect=plain_unauthenticated_error()),
    )
    probe_context.available_kinds = ["company"]

    await PlainPermissionProbe(probe_context).run()

    assert probe_context.status is ProbeStatus.FAILED
    assert "Failed to verify Plain authentication" in (probe_context.message or "")
    client.get_my_permissions.assert_not_called()


@pytest.mark.asyncio
async def test_probe_fails_when_authentication_endpoint_is_unreachable(
    mock_plain_probe: MockPlainProbe,
    probe_context: ProbeContext,
) -> None:
    client = mock_plain_probe.configure_client(
        verify_authentication=AsyncMock(side_effect=request_error()),
    )
    probe_context.available_kinds = ["company"]

    await PlainPermissionProbe(probe_context).run()

    assert probe_context.status is ProbeStatus.FAILED
    assert "could not be reached" in (probe_context.message or "").lower()
    client.get_my_permissions.assert_not_called()


@pytest.mark.asyncio
async def test_probe_marks_checks_failed_when_permissions_fetch_fails(
    mock_plain_probe: MockPlainProbe,
    probe_context: ProbeContext,
) -> None:
    mock_plain_probe.configure_client(
        get_my_permissions=AsyncMock(
            side_effect=PlainGraphQLError([{"message": "boom"}])
        ),
    )
    probe_context.available_kinds = ["company", "tenant"]

    await PlainPermissionProbe(probe_context).run()

    assert len(probe_context.checks) == 2
    assert all(
        check.status is ProbeCheckStatus.FAILURE for check in probe_context.checks
    )
    assert all(
        "fetching API key permissions" in (check.message or "")
        for check in probe_context.checks
    )
