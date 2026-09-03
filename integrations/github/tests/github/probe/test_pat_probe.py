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
    is_fine_grained_pat,
)
from port_ocean.core.probe.context import ProbeContext
from port_ocean.core.probe.models import ProbeCheckStatus


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
async def test_classic_pat_probe_with_configured_organization_skips_org_listing(
    mock_update_progress: AsyncMock,
) -> None:
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

    probe = GitHubPatPermissionProbe(context, [authenticator])
    await probe.run()

    mock_client.get.assert_awaited_once()
    assert mock_client.get.call_args.args[0].endswith("/user")
    assert all(check.scopes == {} for check in context.checks)
    mock_update_progress.assert_awaited()
