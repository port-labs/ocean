import httpx
import jwt
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    GitHubAppToken,
)
from github.helpers.exceptions import AuthenticationException
from github.probe.app.permissions import AppKindPermissionVerdict
from github.probe.app.probe import (
    MISSING_PERMISSIONS_MESSAGE,
    GitHubAppPermissionProbe,
    format_app_probe_auth_error,
)
from port_ocean.core.probe.context import ProbeContext
from port_ocean.core.probe.models import ProbeCheckStatus, ProbeStatus


def _authentication_exception_from_response(
    response: httpx.Response,
) -> AuthenticationException:
    request = httpx.Request(
        "POST", "https://api.github.com/app/installations/1/access_tokens"
    )
    response = httpx.Response(
        response.status_code,
        headers=response.headers,
        json=response.json() if response.content else None,
        request=request,
    )
    http_error = httpx.HTTPStatusError(
        "error",
        request=request,
        response=response,
    )
    try:
        raise AuthenticationException(
            f"Failed to fetch installation token: {http_error}"
        ) from http_error
    except AuthenticationException as error:
        return error


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
async def test_app_probe_fails_org_checks_when_permissions_are_missing(
    mock_update_progress: AsyncMock,
) -> None:
    context = ProbeContext()
    context.available_kinds = ["repository"]
    authenticator = _app_authenticator("my-org")
    authenticator.get_token.return_value = GitHubAppToken(
        token="installation-token",
        permissions=None,
    )

    probe = GitHubAppPermissionProbe(context, [authenticator])
    await probe.run()

    assert context.message is None
    assert len(context.checks) == 1
    assert context.checks[0].scopes == {"org": "my-org"}
    assert context.checks[0].status is ProbeCheckStatus.FAILURE
    assert context.checks[0].message == MISSING_PERMISSIONS_MESSAGE
    mock_update_progress.assert_awaited()


def test_format_app_probe_auth_error_from_http_cause_rate_limit() -> None:
    response = httpx.Response(
        403,
        json={"message": "API rate limit exceeded"},
        headers={
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "1710000000",
        },
    )
    error = _authentication_exception_from_response(response)

    message = format_app_probe_auth_error(error)

    assert (
        message == "Failed to fetch installation token: GitHub API rate limit exceeded"
    )


def test_format_app_probe_auth_error_from_http_cause_unauthorized() -> None:
    response = httpx.Response(401, json={"message": "Bad credentials"})
    error = _authentication_exception_from_response(response)

    message = format_app_probe_auth_error(error)

    assert message == (
        "Failed to fetch installation token: GitHub App credentials are "
        "invalid. Please verify the GitHub App ID and private key are correct."
    )


def test_format_app_probe_auth_error_without_http_cause_falls_back() -> None:
    message = format_app_probe_auth_error(
        AuthenticationException("installation not found")
    )

    assert message == "Failed to fetch installation token: installation not found"


def test_format_app_probe_auth_error_avoids_double_prefixing_auth_exception() -> None:
    message = format_app_probe_auth_error(
        AuthenticationException(
            "Failed to fetch installation token: Connection timeout"
        )
    )

    assert message == "Failed to fetch installation token: Connection timeout"


def test_format_app_probe_auth_error_rewrites_jwt_key_failure() -> None:
    message = format_app_probe_auth_error(
        jwt.InvalidKeyError("Could not parse the provided public key."),
        action="Failed to list GitHub App installations",
    )

    assert message == (
        "Failed to list GitHub App installations: GitHub App credentials are "
        "invalid. Please verify the GitHub App ID and private key are correct."
    )


def test_format_app_probe_auth_error_http_401_matches_local_credentials_message() -> (
    None
):
    http_message = format_app_probe_auth_error(
        _authentication_exception_from_response(
            httpx.Response(401, json={"message": "Bad credentials"})
        ),
        action="Failed to list GitHub App installations",
    )
    local_message = format_app_probe_auth_error(
        jwt.InvalidKeyError("Could not parse the provided public key."),
        action="Failed to list GitHub App installations",
    )

    assert http_message == local_message


@pytest.mark.asyncio
@patch(
    "port_ocean.core.probe.context.ProbeContext.update_progress",
    new_callable=AsyncMock,
)
async def test_app_probe_fails_org_checks_when_token_fetch_raises_authentication_error(
    mock_update_progress: AsyncMock,
) -> None:
    context = ProbeContext()
    context.available_kinds = ["repository"]
    authenticator = _app_authenticator("my-org")
    authenticator.get_token.side_effect = _authentication_exception_from_response(
        httpx.Response(401, json={"message": "Bad credentials"})
    )

    probe = GitHubAppPermissionProbe(context, [authenticator])
    await probe.run()

    assert context.status is ProbeStatus.IN_PROGRESS
    assert context.message is None
    assert len(context.checks) == 1
    assert context.checks[0].scopes == {"org": "my-org"}
    assert context.checks[0].status is ProbeCheckStatus.FAILURE
    assert context.checks[0].message == (
        "Failed to fetch installation token: GitHub App credentials are "
        "invalid. Please verify the GitHub App ID and private key are correct."
    )
    mock_update_progress.assert_awaited()


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
    authenticator.get_token.return_value = GitHubAppToken(
        token="installation-token",
        permissions={"metadata": "read"},
    )

    probe = GitHubAppPermissionProbe(context, [authenticator])
    await probe.run()

    assert len(context.checks) == 1
    assert context.checks[0].scopes == {"org": "my-org"}
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
    org_a.get_token.return_value = GitHubAppToken(
        token="token-a",
        permissions={"metadata": "read", "members": "read"},
    )
    org_b = _app_authenticator("org-b")
    org_b.get_token.return_value = GitHubAppToken(
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
