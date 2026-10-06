from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.exceptions.identity_propagation import (
    OAuthError,
    OAuthProviderNotConfiguredError,
)
from port_ocean.identity_propagation.oauth_broker import providers as providers_module
from port_ocean.identity_propagation.oauth_broker.providers import (
    OAuth2Provider,
    require_provider,
)


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


def _provider(
    *,
    authorize_url: str = "https://idp.example.com/oauth/authorize",
    token_url: str = "https://idp.example.com/oauth/token",
    scopes: str = "read",
) -> OAuth2Provider:
    """Generic fixture — core tests must not encode real integration IdPs."""
    return OAuth2Provider(
        target="example-integration",
        authorize_url=authorize_url,
        token_url=token_url,
        client_id="id",
        client_secret="secret",
        scopes=scopes,
    )


def test_require_provider_returns_the_registered_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider()
    mock_ocean = MagicMock()
    mock_ocean.app.oauth_provider = provider
    monkeypatch.setattr("port_ocean.context.ocean.ocean", mock_ocean)

    assert require_provider() is provider


def test_require_provider_raises_when_none_registered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_ocean = MagicMock()
    mock_ocean.app.oauth_provider = None
    monkeypatch.setattr("port_ocean.context.ocean.ocean", mock_ocean)

    with pytest.raises(OAuthProviderNotConfiguredError):
        require_provider()


def test_authorization_url_carries_state_scopes_and_response_type() -> None:
    url = _provider(scopes="").authorization_url(
        "https://ocean.acme.com/v1/oauth/callback", "signed-state"
    )

    assert url.startswith("https://idp.example.com/oauth/authorize?")
    assert "state=signed-state" in url
    assert "scope=" in url
    assert "response_type=code" in url


def test_authorization_url_uses_the_configured_authorize_endpoint() -> None:
    provider = _provider(
        authorize_url="https://idp.acme.com/oauth/authorize",
        token_url="https://idp.acme.com/oauth/token",
    )

    assert provider.authorization_url("https://cb", "s").startswith(
        "https://idp.acme.com/oauth/authorize?"
    )


def test_authorization_url_includes_configured_scopes() -> None:
    url = _provider(scopes="read offline_access").authorization_url("https://cb", "s")

    assert "offline_access" in url
    assert "read" in url


async def test_exchange_code_returns_the_full_record(
    mock_http_client: MagicMock,
) -> None:
    mock_http_client.post.return_value = token_response(
        {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 3600,
        }
    )

    record = await _provider(scopes="").exchange_code("auth-code", "https://cb")

    assert record.access_token == "access-token"
    assert record.refresh_token == "refresh-token"
    assert record.expires_at is not None
    _, kwargs = mock_http_client.post.call_args
    assert kwargs["data"]["grant_type"] == "authorization_code"
    assert kwargs["data"]["code"] == "auth-code"
    assert kwargs["data"]["scope"] == ""


async def test_refresh_uses_the_refresh_grant(mock_http_client: MagicMock) -> None:
    mock_http_client.post.return_value = token_response(
        {"access_token": "access-new", "refresh_token": "refresh-rotated"}
    )

    record = await _provider().refresh("refresh-old")

    assert record.access_token == "access-new"
    assert record.refresh_token == "refresh-rotated"
    assert record.expires_at is None
    _, kwargs = mock_http_client.post.call_args
    assert kwargs["data"]["grant_type"] == "refresh_token"
    assert kwargs["data"]["refresh_token"] == "refresh-old"


async def test_exchange_code_includes_configured_scopes(
    mock_http_client: MagicMock,
) -> None:
    mock_http_client.post.return_value = token_response(
        {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 3600,
        }
    )

    await _provider(scopes="read offline_access").exchange_code(
        "auth-code", "https://cb"
    )

    _, kwargs = mock_http_client.post.call_args
    assert kwargs["data"]["scope"] == "read offline_access"


async def test_an_error_body_with_a_200_is_still_a_failure(
    mock_http_client: MagicMock,
) -> None:
    # Some IdPs answer 200 with an error body instead of a 4xx.
    mock_http_client.post.return_value = token_response(
        {"error": "bad_verification_code"}
    )

    with pytest.raises(OAuthError):
        await _provider().exchange_code("code", "https://cb")


async def test_an_error_status_is_a_failure(mock_http_client: MagicMock) -> None:
    mock_http_client.post.return_value = token_response({}, status_code=401)

    with pytest.raises(OAuthError):
        await _provider().refresh("refresh-revoked")


async def test_a_transport_failure_is_a_failure(mock_http_client: MagicMock) -> None:
    mock_http_client.post.side_effect = Exception("connection reset")

    with pytest.raises(OAuthError):
        await _provider().refresh("refresh-old")


async def test_a_non_json_body_is_a_failure(mock_http_client: MagicMock) -> None:
    response = MagicMock()
    response.status_code = 200
    response.json = MagicMock(side_effect=ValueError("not json"))
    mock_http_client.post.return_value = response

    with pytest.raises(OAuthError, match="not valid JSON"):
        await _provider().exchange_code("code", "https://cb")
