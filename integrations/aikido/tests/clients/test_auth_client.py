import asyncio
import time
from typing import Any
import pytest
from httpx import HTTPStatusError, Response, Request
from unittest.mock import AsyncMock, MagicMock, patch
from clients.auth_client import AikidoAuth
from helpers.exceptions import MissingIntegrationCredentialException
from port_ocean.utils import http_async_client


@pytest.mark.asyncio
async def test_generate_oauth_token_success() -> None:
    auth = AikidoAuth("https://api.example.com", "id", "secret", http_async_client)
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "abc", "expires_in": 3600}
    mock_response.raise_for_status.return_value = None

    with patch.object(http_async_client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        await auth._generate_oauth_token()
        token = await auth.get_token()

        assert token == "abc"
        assert auth._access_token == "abc"
        assert auth._token_expiry > time.time()
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_generate_oauth_token_custom_expiry() -> None:
    auth = AikidoAuth("https://api.example.com", "id", "secret", http_async_client)
    expires_in = 7200
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "xyz", "expires_in": expires_in}
    mock_response.raise_for_status.return_value = None

    with patch.object(http_async_client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        start = time.time()
        await auth._generate_oauth_token()
        token = await auth.get_token()

        expected_expiry = start + expires_in - 60
        assert abs(auth._token_expiry - expected_expiry) < 2
        assert token == "xyz"


@pytest.mark.asyncio
async def test_generate_oauth_token_failure() -> None:
    auth = AikidoAuth("https://api.example.com", "id", "secret", http_async_client)
    req = Request("POST", "https://api.example.com/oauth/token")
    res = Response(status_code=401, request=req)

    with patch.object(http_async_client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = HTTPStatusError(
            "unauthorized", request=req, response=res
        )

        with pytest.raises(HTTPStatusError):
            await auth._generate_oauth_token()


def test_missing_credentials_raises() -> None:
    with pytest.raises(MissingIntegrationCredentialException):
        AikidoAuth("https://api.example.com", "", "", http_async_client)


@pytest.mark.asyncio
async def test_concurrent_token_refresh_only_calls_once() -> None:
    """Test that multiple concurrent get_token() calls only refresh token once"""
    auth = AikidoAuth("https://api.example.com", "id", "secret", http_async_client)

    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "abc", "expires_in": 3600}
    mock_response.raise_for_status.return_value = None

    with patch.object(http_async_client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        results = await asyncio.gather(
            auth.get_token(), auth.get_token(), auth.get_token()
        )
        assert all(token == "abc" for token in results)
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_token_refresh_serialized_with_lock() -> None:
    """Test that token refresh is properly serialized with the lock"""
    auth = AikidoAuth("https://api.example.com", "id", "secret", http_async_client)

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = {"access_token": "abc", "expires_in": 3600}
    mock_response.raise_for_status.return_value = None

    async def delayed_post(*args: Any, **kwargs: Any) -> MagicMock:
        await asyncio.sleep(0.1)
        return mock_response

    with patch.object(http_async_client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = delayed_post

        tasks = [
            asyncio.create_task(auth.get_token()),
            asyncio.create_task(auth.get_token()),
            asyncio.create_task(auth.get_token()),
        ]

        results = await asyncio.gather(*tasks)

        assert all(token == "abc" for token in results)
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_expired_token_triggers_refresh() -> None:
    """Test that an expired token triggers a refresh"""
    auth = AikidoAuth("https://api.example.com", "id", "secret", http_async_client)

    auth._access_token = "old_token"
    auth._token_expiry = time.time() - 10

    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "new_token", "expires_in": 3600}
    mock_response.raise_for_status.return_value = None

    with patch.object(http_async_client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        token1 = await auth.get_token()
        assert token1 == "new_token"

        token2 = await auth.get_token()
        assert token2 == "new_token"

        # Should only make one API call
        mock_post.assert_called_once()
