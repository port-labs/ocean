from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.clients.auth.personal_access_token_authenticator import (
    PersonalTokenAuthenticator,
)
from github.probe.pat.probe import (
    FINE_GRAINED_PAT_MESSAGE,
    MALFORMED_FINE_GRAINED_PAT_MESSAGE,
    GitHubPatPermissionProbe,
    expand_pat_scopes,
    is_fine_grained_pat,
)
from port_ocean.core.probe.context import ProbeContext
from port_ocean.core.probe.models import ProbeCheckStatus, ProbeStatus


_VALID_FINE_GRAINED_PAT = (
    "github_pat_" + ("a" * 22) + "_" + ("b" * 59)
)


@pytest.mark.parametrize(
    "token, expected",
    [
        (_VALID_FINE_GRAINED_PAT, True),
        ("github_pat_abc123", False),
        ("github_pat_" + ("a" * 22) + "_" + ("b" * 58), False),
        ("github_pat_" + ("a" * 22) + "_" + ("b" * 60), False),
        ("github_pat_" + ("a" * 21) + "_" + ("b" * 59), False),
        ("github_pat_" + ("a" * 22) + ("b" * 59), False),
        ("ghp_classic_token_with_enough_padding_here!", False),
        ("", False),
    ],
)
def test_is_fine_grained_pat(token: str, expected: bool) -> None:
    # Act + Assert
    assert is_fine_grained_pat(token) is expected


def test_expand_pat_scopes_includes_implied_scopes() -> None:
    expanded = expand_pat_scopes({"repo", "admin:org"})

    assert "repo" in expanded
    assert "public_repo" in expanded
    assert "admin:org" in expanded
    assert "read:org" in expanded
    assert "write:org" in expanded


def test_expand_pat_scopes_leaves_unmapped_scopes_unchanged() -> None:
    expanded = expand_pat_scopes({"gist"})

    assert expanded == {"gist"}


@pytest.mark.asyncio
async def test_fine_grained_pat_probe_sets_message_without_api_calls() -> None:
    # Arrange
    context = ProbeContext()
    authenticator = PersonalTokenAuthenticator(_VALID_FINE_GRAINED_PAT)
    mock_client = MagicMock()
    mock_client.get = AsyncMock()
    authenticator._http_client = mock_client

    # Act
    probe = GitHubPatPermissionProbe(context, [authenticator])
    await probe.run()

    # Assert
    assert context.message == FINE_GRAINED_PAT_MESSAGE
    mock_client.get.assert_not_called()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_malformed_fine_grained_pat_probe_fails_without_api_calls(
    mock_update_progress: AsyncMock,
) -> None:
    # Arrange
    context = ProbeContext()
    authenticator = PersonalTokenAuthenticator("github_pat_abc123")
    mock_client = MagicMock()
    mock_client.get = AsyncMock()
    authenticator._http_client = mock_client

    # Act
    probe = GitHubPatPermissionProbe(context, [authenticator])
    await probe.run()

    # Assert
    assert context.status is ProbeStatus.FAILED
    assert context.message == MALFORMED_FINE_GRAINED_PAT_MESSAGE
    mock_client.get.assert_not_called()
    mock_update_progress.assert_awaited()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_classic_pat_probe_fetches_user_once(
    mock_update_progress: AsyncMock,
) -> None:
    context = ProbeContext()
    context.available_kinds = ["repository"]

    authenticator = PersonalTokenAuthenticator("ghp_classic_token")
    user_response = httpx.Response(
        200,
        json={"login": "octocat"},
        headers={"x-oauth-scopes": "repo, read:org"},
    )
    orgs_response = httpx.Response(
        200,
        json=[{"login": "my-org"}],
    )
    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=[user_response, orgs_response])
    authenticator._http_client = mock_client

    probe = GitHubPatPermissionProbe(context, [authenticator])
    await probe.run()

    assert mock_client.get.call_count == 2
    assert mock_client.get.call_args_list[0].args[0].endswith("/user")
    assert mock_client.get.call_args_list[1].args[0].endswith("/user/orgs")
    assert all(check.status is ProbeCheckStatus.SUCCESS for check in context.checks)
    mock_update_progress.assert_awaited()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_classic_pat_probe_with_read_org_validates_membership(
    mock_update_progress: AsyncMock,
) -> None:
    # Arrange
    context = ProbeContext()
    context.available_kinds = ["repository"]

    authenticator = PersonalTokenAuthenticator(
        "ghp_classic_token", organization="my-org"
    )
    user_response = httpx.Response(
        200,
        json={"login": "octocat"},
        headers={"x-oauth-scopes": "repo, read:org"},
    )
    membership_response = httpx.Response(200, json={"state": "active"})
    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=[user_response, membership_response])
    authenticator._http_client = mock_client

    # Act
    probe = GitHubPatPermissionProbe(context, [authenticator])
    await probe.run()

    # Assert
    assert mock_client.get.call_count == 2
    assert mock_client.get.call_args_list[0].args[0].endswith("/user")
    assert (
        mock_client.get.call_args_list[1]
        .args[0]
        .endswith("/user/memberships/orgs/my-org")
    )
    assert all(check.scopes == {"org": "my-org"} for check in context.checks)
    assert all(check.status is ProbeCheckStatus.SUCCESS for check in context.checks)
    mock_update_progress.assert_awaited()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_classic_pat_probe_fails_without_read_org_for_configured_organization(
    mock_update_progress: AsyncMock,
) -> None:
    # Arrange
    context = ProbeContext()
    context.available_kinds = ["repository"]

    authenticator = PersonalTokenAuthenticator(
        "ghp_classic_token", organization="my-org"
    )
    user_response = httpx.Response(
        200,
        json={"login": "octocat"},
        headers={"x-oauth-scopes": "repo"},
    )
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=user_response)
    authenticator._http_client = mock_client

    # Act
    probe = GitHubPatPermissionProbe(context, [authenticator])
    await probe.run()

    # Assert
    mock_client.get.assert_awaited_once()
    assert context.status is ProbeStatus.FAILED
    assert context.message == (
        "Token does not have the 'read:org' scope, unable to validate access to org my-org"
    )
    assert context.checks == []
    mock_update_progress.assert_awaited()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_classic_pat_probe_fails_without_read_org_when_listing_organizations(
    mock_update_progress: AsyncMock,
) -> None:
    # Arrange
    context = ProbeContext()
    context.available_kinds = ["repository"]

    authenticator = PersonalTokenAuthenticator("ghp_classic_token")
    user_response = httpx.Response(
        200,
        json={"login": "octocat"},
        headers={"x-oauth-scopes": "repo"},
    )
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=user_response)
    authenticator._http_client = mock_client

    # Act
    probe = GitHubPatPermissionProbe(context, [authenticator])
    await probe.run()

    # Assert
    mock_client.get.assert_awaited_once()
    assert context.status is ProbeStatus.FAILED
    assert context.message == (
        "Token does not have the 'read:org' scope, unable to fetch accessible organizations"
    )
    assert context.checks == []
    mock_update_progress.assert_awaited()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_classic_pat_probe_with_configured_personal_account_succeeds(
    mock_update_progress: AsyncMock,
) -> None:
    # Arrange
    context = ProbeContext()
    context.available_kinds = ["repository"]

    authenticator = PersonalTokenAuthenticator(
        "ghp_classic_token", organization="octocat"
    )
    user_response = httpx.Response(
        200,
        json={"login": "octocat"},
        headers={"x-oauth-scopes": "repo"},
    )
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=user_response)
    authenticator._http_client = mock_client

    # Act
    probe = GitHubPatPermissionProbe(context, [authenticator])
    await probe.run()

    # Assert
    mock_client.get.assert_awaited_once()
    assert mock_client.get.call_args.args[0].endswith("/user")
    assert all(check.scopes == {"org": "octocat"} for check in context.checks)
    assert all(check.status is ProbeCheckStatus.SUCCESS for check in context.checks)
    mock_update_progress.assert_awaited()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_classic_pat_probe_fails_when_configured_organization_membership_is_pending(
    mock_update_progress: AsyncMock,
) -> None:
    # Arrange
    context = ProbeContext()
    context.available_kinds = ["repository"]

    authenticator = PersonalTokenAuthenticator(
        "ghp_classic_token", organization="pending-org"
    )
    user_response = httpx.Response(
        200,
        json={"login": "octocat"},
        headers={"x-oauth-scopes": "repo, read:org"},
    )
    membership_response = httpx.Response(200, json={"state": "pending"})
    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=[user_response, membership_response])
    authenticator._http_client = mock_client

    # Act
    probe = GitHubPatPermissionProbe(context, [authenticator])
    await probe.run()

    # Assert
    assert context.status is ProbeStatus.FAILED
    assert context.message == (
        "Configured organization 'pending-org' has a pending membership "
        "that has not been accepted yet"
    )
    assert context.checks == []
    mock_update_progress.assert_awaited()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_classic_pat_probe_fails_when_configured_organization_is_inaccessible(
    mock_update_progress: AsyncMock,
) -> None:
    # Arrange
    context = ProbeContext()
    context.available_kinds = ["repository"]

    authenticator = PersonalTokenAuthenticator(
        "ghp_classic_token", organization="wrong-org"
    )
    user_response = httpx.Response(
        200,
        json={"login": "octocat"},
        headers={"x-oauth-scopes": "repo, read:org"},
    )
    membership_response = httpx.Response(404, json={"message": "Not Found"})
    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=[user_response, membership_response])
    authenticator._http_client = mock_client

    # Act
    probe = GitHubPatPermissionProbe(context, [authenticator])
    await probe.run()

    # Assert
    assert context.status is ProbeStatus.FAILED
    assert context.message == (
        "Configured organization 'wrong-org' was not found "
        "or the token does not have access to it"
    )
    assert context.checks == []
    mock_update_progress.assert_awaited()
