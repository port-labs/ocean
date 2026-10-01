from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.exceptions.identity_propagation import OAuthError
from port_ocean.identity_propagation.oauth_broker import providers as providers_module
from port_ocean.identity_propagation.oauth_broker.providers import OAuth2Provider


@pytest.fixture
def mock_http_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    client = MagicMock()
    client.post = AsyncMock()
    monkeypatch.setattr(providers_module, "http_async_client", client)
    return client


def token_response(body: dict[str, Any], status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json = MagicMock(return_value=body)
    return response


def _github_provider() -> OAuth2Provider:
    return OAuth2Provider(
        target="github-ocean",
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        client_id="id",
        client_secret="secret",
        scopes="",
    )


def _gitlab_provider(host: str = "https://gitlab.com") -> OAuth2Provider:
    return OAuth2Provider(
        target="gitlab-v2",
        authorize_url=f"{host}/oauth/authorize",
        token_url=f"{host}/oauth/token",
        client_id="id",
        client_secret="secret",
        scopes="api",
    )


def _azure_devops_provider(tenant_id: str = "tenant-1") -> OAuth2Provider:
    return OAuth2Provider(
        target="azure-devops",
        authorize_url=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize",
        token_url=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        client_id="id",
        client_secret="secret",
        scopes="499b84ac-1321-427f-aa17-267ca6975798/user_impersonation offline_access",
    )


def test_github_authorization_url_carries_the_state_and_scopes() -> None:
    url = _github_provider().authorization_url(
        "https://ocean.acme.com/v1/oauth/callback", "signed-state"
    )

    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "state=signed-state" in url
    # empty for GitHub Apps; permissions come from the App Manifest
    assert "scope=" in url
    assert "response_type=code" in url


def test_gitlab_endpoints_follow_the_configured_host() -> None:
    provider = _gitlab_provider(host="https://gitlab.acme.com")

    assert provider.authorization_url("https://cb", "s").startswith(
        "https://gitlab.acme.com/oauth/authorize?"
    )


def test_azure_devops_requests_offline_access_so_refresh_is_possible() -> None:
    url = _azure_devops_provider().authorization_url("https://cb", "s")

    assert "login.microsoftonline.com/tenant-1/oauth2/v2.0/authorize" in url
    assert "offline_access" in url


async def test_exchange_code_returns_the_full_record(
    mock_http_client: MagicMock,
) -> None:
    mock_http_client.post.return_value = token_response(
        {
            "access_token": "gho_token",
            "refresh_token": "ghr_token",
            "expires_in": 3600,
        }
    )

    record = await _github_provider().exchange_code("auth-code", "https://cb")

    assert record.access_token == "gho_token"
    assert record.refresh_token == "ghr_token"
    assert record.expires_at is not None
    _, kwargs = mock_http_client.post.call_args
    assert kwargs["data"]["grant_type"] == "authorization_code"
    assert kwargs["data"]["code"] == "auth-code"
    assert kwargs["data"]["scope"] == ""


async def test_refresh_uses_the_refresh_grant(mock_http_client: MagicMock) -> None:
    mock_http_client.post.return_value = token_response(
        {"access_token": "gho_new", "refresh_token": "ghr_rotated"}
    )

    record = await _github_provider().refresh("ghr_old")

    assert record.access_token == "gho_new"
    assert record.refresh_token == "ghr_rotated"
    assert record.expires_at is None
    _, kwargs = mock_http_client.post.call_args
    assert kwargs["data"]["grant_type"] == "refresh_token"
    assert kwargs["data"]["refresh_token"] == "ghr_old"


async def test_azure_exchange_code_includes_scope(
    mock_http_client: MagicMock,
) -> None:
    mock_http_client.post.return_value = token_response(
        {
            "access_token": "ado_token",
            "refresh_token": "ado_refresh",
            "expires_in": 3600,
        }
    )

    await _azure_devops_provider().exchange_code("auth-code", "https://cb")

    _, kwargs = mock_http_client.post.call_args
    assert "499b84ac" in kwargs["data"]["scope"]
    assert "offline_access" in kwargs["data"]["scope"]


async def test_an_error_body_with_a_200_is_still_a_failure(
    mock_http_client: MagicMock,
) -> None:
    # Some providers (e.g. GitHub) answer 200 with an error body instead of a 4xx.
    mock_http_client.post.return_value = token_response(
        {"error": "bad_verification_code"}
    )

    with pytest.raises(OAuthError):
        await _github_provider().exchange_code("code", "https://cb")


async def test_an_error_status_is_a_failure(mock_http_client: MagicMock) -> None:
    mock_http_client.post.return_value = token_response({}, status_code=401)

    with pytest.raises(OAuthError):
        await _github_provider().refresh("ghr_revoked")


async def test_a_transport_failure_is_a_failure(mock_http_client: MagicMock) -> None:
    mock_http_client.post.side_effect = Exception("connection reset")

    with pytest.raises(OAuthError):
        await _github_provider().refresh("ghr_old")
