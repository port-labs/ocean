from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from jira.probe.probe import JiraPermissionProbe
from kinds import Kinds
from port_ocean.core.probe import ProbeCheckStatus, ProbeContext, ProbeStatus


def http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.atlassian.net/rest/api/3/myself")
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=request,
        response=httpx.Response(status_code, request=request),
    )


def _mock_client(**kwargs: Any) -> SimpleNamespace:
    defaults: dict[str, Any] = {
        "verify_current_user": AsyncMock(),
        "get_current_user_permissions": AsyncMock(return_value={}),
        "verify_teams_access": AsyncMock(),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_probe_resolves_permission_checks_for_available_kinds(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
) -> None:
    client = _mock_client(
        get_current_user_permissions=AsyncMock(
            return_value={
                "BROWSE_PROJECTS": True,
                "USER_PICKER": False,
            }
        ),
    )
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"atlassian_organization_id": "test-org-id"}
    monkeypatch.setattr("jira.probe.probe.ocean", mock_ocean)
    monkeypatch.setattr(
        "jira.probe.probe.get_or_create_jira_client",
        lambda: client,
    )
    probe_context.available_kinds = ["project", "user", "team"]

    await JiraPermissionProbe(probe_context).run()

    client.verify_current_user.assert_awaited_once()
    client.get_current_user_permissions.assert_awaited_once()
    assert set(client.get_current_user_permissions.await_args.args[0]) == {
        "BROWSE_PROJECTS",
        "USER_PICKER",
    }
    client.verify_teams_access.assert_awaited_once_with("test-org-id")
    assert [check.status for check in probe_context.checks] == [
        ProbeCheckStatus.SUCCESS,
        ProbeCheckStatus.FAILURE,
        ProbeCheckStatus.SUCCESS,
    ]
    assert probe_context.checks[0].message == "Permission(s) granted: BROWSE_PROJECTS"
    assert probe_context.checks[1].message == "Missing permission(s): USER_PICKER"
    assert probe_context.checks[2].message == "Atlassian Teams API access verified"


@pytest.mark.asyncio
async def test_probe_deduplicates_permission_keys(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
) -> None:
    client = _mock_client(
        get_current_user_permissions=AsyncMock(return_value={"BROWSE_PROJECTS": True}),
    )
    monkeypatch.setattr(
        "jira.probe.probe.get_or_create_jira_client",
        lambda: client,
    )
    probe_context.available_kinds = ["project", "issue", "board"]

    await JiraPermissionProbe(probe_context).run()

    client.get_current_user_permissions.assert_awaited_once_with(["BROWSE_PROJECTS"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        http_status_error(401),
        httpx.ConnectError("connection refused"),
    ],
)
async def test_probe_fails_when_authentication_cannot_be_verified(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    error: Exception,
) -> None:
    client = _mock_client(verify_current_user=AsyncMock(side_effect=error))
    monkeypatch.setattr(
        "jira.probe.probe.get_or_create_jira_client",
        lambda: client,
    )
    probe_context.available_kinds = ["project", "user"]

    await JiraPermissionProbe(probe_context).run()

    assert probe_context.status is ProbeStatus.FAILED
    assert probe_context.message == "Failed to verify Jira authentication."
    assert probe_context.checks == []
    client.get_current_user_permissions.assert_not_called()


@pytest.mark.asyncio
async def test_probe_marks_permission_checks_failed_when_permission_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
) -> None:
    client = _mock_client(
        get_current_user_permissions=AsyncMock(side_effect=http_status_error(500)),
    )
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"atlassian_organization_id": "test-org-id"}
    monkeypatch.setattr("jira.probe.probe.ocean", mock_ocean)
    monkeypatch.setattr(
        "jira.probe.probe.get_or_create_jira_client",
        lambda: client,
    )
    probe_context.available_kinds = ["project", "user", "team"]

    await JiraPermissionProbe(probe_context).run()

    assert probe_context.status is ProbeStatus.IN_PROGRESS
    assert probe_context.message is None
    assert [check.status for check in probe_context.checks] == [
        ProbeCheckStatus.FAILURE,
        ProbeCheckStatus.FAILURE,
        ProbeCheckStatus.SUCCESS,
    ]
    assert probe_context.checks[0].message == (
        "Jira returned HTTP 500 while fetching user permissions"
    )
    client.verify_teams_access.assert_awaited_once_with("test-org-id")


@pytest.mark.asyncio
async def test_probe_marks_permission_checks_failed_on_connection_error(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
) -> None:
    error = httpx.ConnectError("nodename nor servname provided")
    client = _mock_client(
        get_current_user_permissions=AsyncMock(side_effect=error),
    )
    monkeypatch.setattr(
        "jira.probe.probe.get_or_create_jira_client",
        lambda: client,
    )
    probe_context.available_kinds = ["project"]

    await JiraPermissionProbe(probe_context).run()

    assert probe_context.checks[0].status is ProbeCheckStatus.FAILURE
    assert probe_context.checks[0].message == (
        "Jira could not be reached while fetching user permissions: "
        "nodename nor servname provided"
    )


@pytest.mark.asyncio
async def test_team_probe_verifies_authentication_without_jira_permissions(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
) -> None:
    client = _mock_client()
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"atlassian_organization_id": "test-org-id"}
    monkeypatch.setattr("jira.probe.probe.ocean", mock_ocean)
    monkeypatch.setattr(
        "jira.probe.probe.get_or_create_jira_client",
        lambda: client,
    )
    probe_context.available_kinds = [Kinds.TEAM]

    await JiraPermissionProbe(probe_context).run()

    client.verify_current_user.assert_awaited_once()
    client.get_current_user_permissions.assert_awaited_once_with([])
    client.verify_teams_access.assert_awaited_once_with("test-org-id")
    assert probe_context.checks[0].status is ProbeCheckStatus.SUCCESS


@pytest.mark.asyncio
async def test_team_probe_fails_when_organization_id_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
) -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {}
    monkeypatch.setattr("jira.probe.probe.ocean", mock_ocean)
    client = _mock_client()
    monkeypatch.setattr(
        "jira.probe.probe.get_or_create_jira_client",
        lambda: client,
    )
    probe_context.available_kinds = [Kinds.TEAM]

    await JiraPermissionProbe(probe_context).run()

    client.verify_teams_access.assert_not_called()
    assert probe_context.checks[0].status is ProbeCheckStatus.FAILURE
    assert (
        probe_context.checks[0].message
        == "Atlassian organization ID is required to sync teams"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403, 500])
async def test_team_probe_reports_teams_api_failures(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    status_code: int,
) -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"atlassian_organization_id": "test-org-id"}
    monkeypatch.setattr("jira.probe.probe.ocean", mock_ocean)
    client = _mock_client(
        verify_teams_access=AsyncMock(side_effect=http_status_error(status_code)),
    )
    monkeypatch.setattr(
        "jira.probe.probe.get_or_create_jira_client",
        lambda: client,
    )
    probe_context.available_kinds = [Kinds.TEAM]

    await JiraPermissionProbe(probe_context).run()

    assert probe_context.checks[0].status is ProbeCheckStatus.FAILURE
    assert (
        probe_context.checks[0].message
        == f"Jira returned HTTP {status_code} while verifying teams access"
    )


@pytest.mark.asyncio
async def test_team_probe_reports_teams_api_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
) -> None:
    error = httpx.ConnectError("nodename nor servname provided")
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"atlassian_organization_id": "test-org-id"}
    monkeypatch.setattr("jira.probe.probe.ocean", mock_ocean)
    client = _mock_client(verify_teams_access=AsyncMock(side_effect=error))
    monkeypatch.setattr(
        "jira.probe.probe.get_or_create_jira_client",
        lambda: client,
    )
    probe_context.available_kinds = [Kinds.TEAM]

    await JiraPermissionProbe(probe_context).run()

    assert probe_context.checks[0].status is ProbeCheckStatus.FAILURE
    assert probe_context.checks[0].message == (
        "Jira could not be reached while verifying teams access: "
        "nodename nor servname provided"
    )
