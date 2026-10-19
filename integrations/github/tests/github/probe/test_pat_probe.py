from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.clients.auth.personal_access_token_authenticator import (
    PersonalTokenAuthenticator,
)
from github.probe.pat.probe import (
    FINE_GRAINED_PAT_MESSAGE,
    GitHubPatPermissionProbe,
    expand_pat_scopes,
    format_authenticated_user_error,
    is_fine_grained_pat,
)
from port_ocean.core.probe.context import ProbeContext
from port_ocean.core.probe.models import ProbeCheckStatus, ProbeStatus


@pytest.mark.parametrize(
    "token, expected",
    [
        ("github_pat_abc123", True),
        ("ghp_classic_token", False),
        ("", False),
    ],
)
def test_is_fine_grained_pat(token: str, expected: bool) -> None:
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
    context = ProbeContext()
    authenticator = PersonalTokenAuthenticator("github_pat_test_token")
    mock_client = MagicMock()
    mock_client.get = AsyncMock()
    authenticator._http_client = mock_client

    probe = GitHubPatPermissionProbe(context, [authenticator])
    await probe.run()

    assert context.message == FINE_GRAINED_PAT_MESSAGE
    mock_client.get.assert_not_called()


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


def test_format_authenticated_user_error_rate_limit_from_headers() -> None:
    response = httpx.Response(
        403,
        json={"message": "API rate limit exceeded for user ID 1."},
        headers={
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "1710000000",
        },
    )

    message = format_authenticated_user_error(response)

    assert message == "Failed to fetch authenticated user: GitHub API rate limit exceeded"


def test_format_authenticated_user_error_forbidden_not_rate_limit() -> None:
    response = httpx.Response(
        403,
        json={"message": "Resource not accessible by personal access token"},
        headers={"x-ratelimit-remaining": "4990"},
    )

    message = format_authenticated_user_error(response)

    assert "403" in message
    assert "not a rate limit error" in message
    assert "Resource not accessible by personal access token" in message
    assert "rate limit exceeded" not in message.casefold()


def test_format_authenticated_user_error_unauthorized() -> None:
    response = httpx.Response(401, json={"message": "Bad credentials"})

    message = format_authenticated_user_error(response)

    assert message == (
        "Failed to fetch authenticated user: GitHub API returned that the "
        "credentials are invalid. Please verify the personal access token is "
        "valid and not expired."
    )


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_classic_pat_probe_fails_with_indicative_401_message(
    mock_update_progress: AsyncMock,
) -> None:
    context = ProbeContext()
    authenticator = PersonalTokenAuthenticator("ghp_bad_token")
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )
    authenticator._http_client = mock_client

    probe = GitHubPatPermissionProbe(context, [authenticator])
    await probe.run()

    assert context.status is ProbeStatus.FAILED
    assert context.message == (
        "Failed to fetch authenticated user: GitHub API returned that the "
        "credentials are invalid. Please verify the personal access token is "
        "valid and not expired."
    )
    mock_update_progress.assert_awaited()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_classic_pat_probe_fails_with_indicative_rate_limit_message(
    mock_update_progress: AsyncMock,
) -> None:
    context = ProbeContext()
    authenticator = PersonalTokenAuthenticator("ghp_classic_token")
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=httpx.Response(
            403,
            json={"message": "API rate limit exceeded"},
            headers={
                "x-ratelimit-remaining": "0",
                "x-ratelimit-reset": "1710000000",
            },
        )
    )
    authenticator._http_client = mock_client

    probe = GitHubPatPermissionProbe(context, [authenticator])
    await probe.run()

    assert context.status is ProbeStatus.FAILED
    assert (
        context.message
        == "Failed to fetch authenticated user: GitHub API rate limit exceeded"
    )
    mock_update_progress.assert_awaited()
