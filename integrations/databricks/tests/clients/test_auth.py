import asyncio
import time
from typing import Any

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from clients.auth import (
    MissingIntegrationCredentialException,
    OAuthM2MAuthenticator,
    TokenAuthenticator,
    build_authenticator,
)


@pytest.mark.asyncio
async def test_token_authenticator_returns_bearer_header() -> None:
    authenticator = TokenAuthenticator("my-pat-token")
    header = await authenticator.get_auth_header()
    assert header == {"Authorization": "Bearer my-pat-token"}


def test_token_authenticator_requires_token() -> None:
    with pytest.raises(MissingIntegrationCredentialException):
        TokenAuthenticator("")


def test_oauth_authenticator_requires_credentials() -> None:
    with pytest.raises(MissingIntegrationCredentialException):
        OAuthM2MAuthenticator(
            "https://workspace.cloud.databricks.com", "", "", httpx.AsyncClient()
        )


@pytest.mark.asyncio
async def test_oauth_authenticator_first_fetch() -> None:
    http_client = httpx.AsyncClient()
    authenticator = OAuthM2MAuthenticator(
        "https://workspace.cloud.databricks.com", "id", "secret", http_client
    )

    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "abc", "expires_in": 3600}
    mock_response.raise_for_status.return_value = None

    with patch.object(http_client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        header = await authenticator.get_auth_header()

        assert header == {"Authorization": "Bearer abc"}
        mock_post.assert_called_once()
        called_url = mock_post.call_args.args[0]
        assert called_url == "https://workspace.cloud.databricks.com/oidc/v1/token"


@pytest.mark.asyncio
async def test_oauth_authenticator_cache_hit_within_expiry() -> None:
    http_client = httpx.AsyncClient()
    authenticator = OAuthM2MAuthenticator(
        "https://workspace.cloud.databricks.com", "id", "secret", http_client
    )

    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "abc", "expires_in": 3600}
    mock_response.raise_for_status.return_value = None

    with patch.object(http_client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        await authenticator.get_auth_header()
        await authenticator.get_auth_header()
        await authenticator.get_auth_header()

        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_oauth_authenticator_refresh_after_expiry() -> None:
    http_client = httpx.AsyncClient()
    authenticator = OAuthM2MAuthenticator(
        "https://workspace.cloud.databricks.com", "id", "secret", http_client
    )
    authenticator._access_token = "old-token"
    authenticator._token_expiry = time.time() - 10

    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "new-token", "expires_in": 3600}
    mock_response.raise_for_status.return_value = None

    with patch.object(http_client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        header = await authenticator.get_auth_header()

        assert header == {"Authorization": "Bearer new-token"}
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_oauth_authenticator_concurrent_calls_only_fetch_once() -> None:
    http_client = httpx.AsyncClient()
    authenticator = OAuthM2MAuthenticator(
        "https://workspace.cloud.databricks.com", "id", "secret", http_client
    )

    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "abc", "expires_in": 3600}
    mock_response.raise_for_status.return_value = None

    async def delayed_post(*args: Any, **kwargs: Any) -> MagicMock:
        await asyncio.sleep(0.05)
        return mock_response

    with patch.object(http_client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = delayed_post

        results = await asyncio.gather(
            authenticator.get_auth_header(),
            authenticator.get_auth_header(),
            authenticator.get_auth_header(),
        )

        assert all(result == {"Authorization": "Bearer abc"} for result in results)
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_oauth_authenticator_failure_path_surfaces_error() -> None:
    http_client = httpx.AsyncClient()
    authenticator = OAuthM2MAuthenticator(
        "https://workspace.cloud.databricks.com", "id", "secret", http_client
    )

    request = httpx.Request(
        "POST", "https://workspace.cloud.databricks.com/oidc/v1/token"
    )
    response = httpx.Response(status_code=401, request=request)

    with patch.object(http_client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "unauthorized", request=request, response=response
        )

        with pytest.raises(httpx.HTTPStatusError):
            await authenticator.get_auth_header()


def test_build_authenticator_prefers_token() -> None:
    authenticator = build_authenticator(
        workspace_url="https://workspace.cloud.databricks.com",
        token="my-token",
        client_id="id",
        client_secret="secret",
        http_client=httpx.AsyncClient(),
    )
    assert isinstance(authenticator, TokenAuthenticator)


def test_build_authenticator_uses_oauth_when_no_token() -> None:
    authenticator = build_authenticator(
        workspace_url="https://workspace.cloud.databricks.com",
        token=None,
        client_id="id",
        client_secret="secret",
        http_client=httpx.AsyncClient(),
    )
    assert isinstance(authenticator, OAuthM2MAuthenticator)


def test_build_authenticator_raises_when_no_credentials() -> None:
    with pytest.raises(MissingIntegrationCredentialException):
        build_authenticator(
            workspace_url="https://workspace.cloud.databricks.com",
            token=None,
            client_id=None,
            client_secret=None,
            http_client=httpx.AsyncClient(),
        )
