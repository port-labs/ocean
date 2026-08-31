from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from jira.probe import JiraPermissionProbe
from jira.probe import permissions as probe_permissions
from port_ocean.core.probe import ProbeCheckStatus, ProbeContext, ProbeStatus


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.atlassian.net/rest/api/3/myself")
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=request,
        response=httpx.Response(status_code, request=request),
    )


@pytest.fixture
def mock_ocean_integration_config(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"atlassian_organization_id": "test-org-id"}
    monkeypatch.setattr(probe_permissions, "ocean", mock_ocean)
    return mock_ocean


@pytest.mark.asyncio
async def test_jira_permissions_are_mapped_to_available_kinds(
    monkeypatch: pytest.MonkeyPatch,
    mock_ocean_integration_config: MagicMock,
) -> None:
    client = SimpleNamespace(
        get_current_user_permissions=AsyncMock(
            return_value={
                "BROWSE_PROJECTS": True,
                "USER_PICKER": False,
            }
        ),
        verify_teams_access=AsyncMock(),
    )
    monkeypatch.setattr(probe_permissions, "get_or_create_jira_client", lambda: client)
    context = ProbeContext()
    context.available_kinds = ["project", "user", "team"]
    snapshots: list[list[ProbeCheckStatus]] = []
    monkeypatch.setattr(
        context,
        "update_progress",
        MagicMock(
            side_effect=lambda: snapshots.append(
                [check.status for check in context.checks]
            )
        ),
    )

    await JiraPermissionProbe(context).run()

    client.get_current_user_permissions.assert_awaited_once_with(
        ("BROWSE_PROJECTS", "USER_PICKER")
    )
    client.verify_teams_access.assert_awaited_once_with("test-org-id")
    assert snapshots[0] == [ProbeCheckStatus.PENDING] * 3
    assert snapshots[-1] == [
        ProbeCheckStatus.SUCCESS,
        ProbeCheckStatus.FAILURE,
        ProbeCheckStatus.SUCCESS,
    ]
    assert [check.scopes for check in context.checks] == [{}, {}, {}]
    assert context.checks[0].message == "Jira grants BROWSE_PROJECTS"
    assert context.checks[1].message == "Jira requires USER_PICKER"
    assert context.checks[2].message == "Atlassian Teams API access verified"


@pytest.mark.asyncio
async def test_missing_jira_permission_information_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = SimpleNamespace(get_current_user_permissions=AsyncMock(return_value={}))
    monkeypatch.setattr(probe_permissions, "get_or_create_jira_client", lambda: client)
    context = ProbeContext()
    context.available_kinds = ["project"]

    await JiraPermissionProbe(context).run()

    assert context.checks[0].status is ProbeCheckStatus.UNKNOWN
    assert (
        context.checks[0].message
        == "Jira did not return permission information for BROWSE_PROJECTS"
    )


@pytest.mark.asyncio
async def test_team_probe_verifies_authentication_without_jira_permissions(
    monkeypatch: pytest.MonkeyPatch,
    mock_ocean_integration_config: MagicMock,
) -> None:
    client = SimpleNamespace(
        get_current_user_permissions=AsyncMock(return_value={}),
        verify_teams_access=AsyncMock(),
    )
    monkeypatch.setattr(probe_permissions, "get_or_create_jira_client", lambda: client)
    context = ProbeContext()
    context.available_kinds = ["team"]

    await JiraPermissionProbe(context).run()

    client.get_current_user_permissions.assert_awaited_once_with(())
    client.verify_teams_access.assert_awaited_once_with("test-org-id")
    assert context.checks[0].status is ProbeCheckStatus.SUCCESS
    assert context.checks[0].message == "Atlassian Teams API access verified"


@pytest.mark.asyncio
async def test_team_probe_fails_when_organization_id_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {}
    monkeypatch.setattr(probe_permissions, "ocean", mock_ocean)
    client = SimpleNamespace(
        get_current_user_permissions=AsyncMock(return_value={}),
        verify_teams_access=AsyncMock(),
    )
    monkeypatch.setattr(probe_permissions, "get_or_create_jira_client", lambda: client)
    context = ProbeContext()
    context.available_kinds = ["team"]

    await JiraPermissionProbe(context).run()

    client.verify_teams_access.assert_not_called()
    assert context.checks[0].status is ProbeCheckStatus.FAILURE
    assert (
        context.checks[0].message
        == probe_permissions.TEAM_ORG_ID_MISSING_MESSAGE
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code",
    [401, 403, 500],
)
async def test_team_probe_reports_teams_api_failures(
    monkeypatch: pytest.MonkeyPatch,
    mock_ocean_integration_config: MagicMock,
    status_code: int,
) -> None:
    client = SimpleNamespace(
        get_current_user_permissions=AsyncMock(return_value={}),
        verify_teams_access=AsyncMock(side_effect=_http_status_error(status_code)),
    )
    monkeypatch.setattr(probe_permissions, "get_or_create_jira_client", lambda: client)
    context = ProbeContext()
    context.available_kinds = ["team"]

    await JiraPermissionProbe(context).run()

    assert context.checks[0].status is ProbeCheckStatus.FAILURE
    assert (
        context.checks[0].message
        == f"Jira returned HTTP {status_code} while verifying teams access"
    )


@pytest.mark.asyncio
async def test_team_probe_reports_teams_api_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
    mock_ocean_integration_config: MagicMock,
) -> None:
    error = httpx.ConnectError("nodename nor servname provided")
    client = SimpleNamespace(
        get_current_user_permissions=AsyncMock(return_value={}),
        verify_teams_access=AsyncMock(side_effect=error),
    )
    monkeypatch.setattr(probe_permissions, "get_or_create_jira_client", lambda: client)
    context = ProbeContext()
    context.available_kinds = ["team"]

    await JiraPermissionProbe(context).run()

    assert context.checks[0].status is ProbeCheckStatus.FAILURE
    assert context.checks[0].message == (
        "Jira could not be reached while verifying teams access: "
        "nodename nor servname provided"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error, expected_message",
    [
        (
            _http_status_error(401),
            "Jira rejected the configured credentials with HTTP 401",
        ),
        (
            _http_status_error(403),
            "Jira rejected the configured credentials with HTTP 403",
        ),
        (
            _http_status_error(500),
            "Jira returned HTTP 500 while reading the current user's permissions",
        ),
        (
            httpx.ConnectError("nodename nor servname provided"),
            "Jira could not be reached while reading the current user's permissions: "
            "nodename nor servname provided",
        ),
    ],
)
async def test_failed_permission_lookup_fails_the_probe_with_a_reason(
    monkeypatch: pytest.MonkeyPatch, error: Exception, expected_message: str
) -> None:
    client = SimpleNamespace(get_current_user_permissions=AsyncMock(side_effect=error))
    monkeypatch.setattr(probe_permissions, "get_or_create_jira_client", lambda: client)
    context = ProbeContext()
    context.available_kinds = ["project", "user"]

    await JiraPermissionProbe(context).run()

    assert context.status is ProbeStatus.FAILED
    assert context.message == expected_message
    assert context.checks == []
