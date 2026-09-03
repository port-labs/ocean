import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    GitHubToken,
)
from github.helpers.exceptions import AuthenticationException
from github.probe.app.permissions import AppKindPermissionVerdict
from github.probe.app.probe import (
    MISSING_PERMISSIONS_MESSAGE,
    GitHubAppPermissionProbe,
)
from port_ocean.core.probe.context import ProbeContext
from port_ocean.core.probe.models import ProbeCheckStatus, ProbeStatus


@pytest.mark.parametrize(
    "level, expected",
    [
        ("read", True),
        ("write", True),
        ("admin", True),
        ("none", False),
        ("", False),
    ],
)
def test_app_kind_permission_verdict_treats_read_or_higher_as_granted(
    level: str,
    expected: bool,
) -> None:
    verdict = AppKindPermissionVerdict()

    assert verdict.is_granted("contents", {"contents": level}) is expected


def test_app_kind_permission_verdict_rejects_non_string_levels() -> None:
    verdict = AppKindPermissionVerdict()

    assert verdict.is_granted("contents", {"contents": True}) is False


def test_app_kind_permission_verdict_succeeds_when_any_required_permission_is_granted() -> (
    None
):
    verdict = AppKindPermissionVerdict()

    status, message = verdict.verdict(
        "repository",
        {"metadata": "read", "contents": "none"},
    )

    assert status is ProbeCheckStatus.SUCCESS
    assert "metadata" in message


def test_app_kind_permission_verdict_fails_when_no_required_permission_is_granted() -> (
    None
):
    verdict = AppKindPermissionVerdict()

    status, _ = verdict.verdict(
        "repository",
        {"metadata": "none"},
    )

    assert status is ProbeCheckStatus.FAILURE


def _app_authenticator(organization: str) -> MagicMock:
    authenticator = MagicMock(spec=AbstractGitHubAuthenticator)
    authenticator.organization = organization
    authenticator.get_token = AsyncMock()
    return authenticator


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_app_probe_sets_message_when_permissions_are_missing(
    mock_update_progress: AsyncMock,
) -> None:
    context = ProbeContext()
    authenticator = _app_authenticator("my-org")
    authenticator.get_token.return_value = GitHubToken(token="installation-token")

    probe = GitHubAppPermissionProbe(context, [authenticator])
    await probe.run()

    assert context.message == MISSING_PERMISSIONS_MESSAGE
    assert context.checks == []
    mock_update_progress.assert_not_awaited()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_app_probe_fails_when_token_fetch_raises_authentication_error(
    mock_update_progress: AsyncMock,
) -> None:
    context = ProbeContext()
    authenticator = _app_authenticator("my-org")
    authenticator.get_token.side_effect = AuthenticationException(
        "installation not found"
    )

    probe = GitHubAppPermissionProbe(context, [authenticator])
    await probe.run()

    assert context.status is ProbeStatus.FAILED
    assert context.message == "installation not found"
    assert context.checks == []
    mock_update_progress.assert_awaited_once()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_app_probe_resolves_checks_for_single_installation(
    mock_update_progress: AsyncMock,
) -> None:
    context = ProbeContext()
    context.available_kinds = ["repository"]

    authenticator = _app_authenticator("my-org")
    authenticator.get_token.return_value = GitHubToken(
        token="installation-token",
        permissions={"metadata": "read"},
    )

    probe = GitHubAppPermissionProbe(context, [authenticator])
    await probe.run()

    assert len(context.checks) == 1
    assert context.checks[0].scopes == {}
    assert context.checks[0].status is ProbeCheckStatus.SUCCESS
    mock_update_progress.assert_awaited()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_app_probe_resolves_checks_per_installation_for_multi_org(
    mock_update_progress: AsyncMock,
) -> None:
    context = ProbeContext()
    context.available_kinds = ["repository", "user"]

    org_a = _app_authenticator("org-a")
    org_a.get_token.return_value = GitHubToken(
        token="token-a",
        permissions={"metadata": "read", "members": "read"},
    )
    org_b = _app_authenticator("org-b")
    org_b.get_token.return_value = GitHubToken(
        token="token-b",
        permissions={"metadata": "none"},
    )

    probe = GitHubAppPermissionProbe(context, [org_a, org_b])
    await probe.run()

    assert len(context.checks) == 4
    assert [check.scopes for check in context.checks] == [
        {"org": "org-a"},
        {"org": "org-a"},
        {"org": "org-b"},
        {"org": "org-b"},
    ]
    assert [check.status for check in context.checks] == [
        ProbeCheckStatus.SUCCESS,
        ProbeCheckStatus.SUCCESS,
        ProbeCheckStatus.FAILURE,
        ProbeCheckStatus.FAILURE,
    ]
    mock_update_progress.assert_awaited()
