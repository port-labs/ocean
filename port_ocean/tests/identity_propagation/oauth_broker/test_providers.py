from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.config.settings import OAuthProviderSettings
from port_ocean.exceptions.identity_propagation import OAuthError
from port_ocean.identity_propagation.oauth_broker import providers as providers_module
from port_ocean.identity_propagation.oauth_broker.providers import AZURE_DEVOPS, GITHUB, GITLAB, OAuth2Provider


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


def settings(**overrides: Any) -> OAuthProviderSettings:
    return OAuthProviderSettings(client_id="id", client_secret="secret", **overrides)


def test_github_authorization_url_carries_the_state_and_scopes() -> None:
    url = OAuth2Provider(GITHUB, settings()).authorization_url(
        "https://ocean.acme.com/v1/oauth/callback", "signed-state"
    )

    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "state=signed-state" in url
    assert "scope=" in url  # empty for GitHub Apps; permissions come from the App Manifest
    assert "response_type=code" in url


def test_gitlab_endpoints_follow_the_configured_host() -> None:
    provider = OAuth2Provider(GITLAB, settings(host="https://gitlab.acme.com/"))

    assert provider.authorization_url("https://cb", "s").startswith(
        "https://gitlab.acme.com/oauth/authorize?"
    )


def test_azure_devops_requests_offline_access_so_refresh_is_possible() -> None:
    url = OAuth2Provider(
        AZURE_DEVOPS, settings(tenant_id="tenant-1")
    ).authorization_url("https://cb", "s")

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

    record = await OAuth2Provider(GITHUB, settings()).exchange_code(
        "auth-code", "https://cb"
    )

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

    record = await OAuth2Provider(GITHUB, settings()).refresh("ghr_old")

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
        {"access_token": "ado_token", "refresh_token": "ado_refresh", "expires_in": 3600}
    )

    await OAuth2Provider(AZURE_DEVOPS, settings(tenant_id="tenant-1")).exchange_code(
        "auth-code", "https://cb"
    )

    _, kwargs = mock_http_client.post.call_args
    assert "499b84ac" in kwargs["data"]["scope"]
    assert "offline_access" in kwargs["data"]["scope"]


async def test_an_error_body_with_a_200_is_still_a_failure(
    mock_http_client: MagicMock,
) -> None:
    # GitHub answers 200 with an error body rather than a 4xx.
    mock_http_client.post.return_value = token_response(
        {"error": "bad_verification_code"}
    )

    with pytest.raises(OAuthError):
        await OAuth2Provider(GITHUB, settings()).exchange_code("code", "https://cb")


async def test_an_error_status_is_a_failure(mock_http_client: MagicMock) -> None:
    mock_http_client.post.return_value = token_response({}, status_code=401)

    with pytest.raises(OAuthError):
        await OAuth2Provider(GITHUB, settings()).refresh("ghr_revoked")


async def test_a_transport_failure_is_a_failure(mock_http_client: MagicMock) -> None:
    mock_http_client.post.side_effect = Exception("connection reset")

    with pytest.raises(OAuthError):
        await OAuth2Provider(GITHUB, settings()).refresh("ghr_old")
