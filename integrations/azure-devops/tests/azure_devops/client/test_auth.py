import asyncio
import base64
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import Response

from azure_devops.client.auth import (
    ADO_SCOPE,
    PatAuthProvider,
    ServicePrincipalAuthProvider,
    ServicePrincipalTokenManager,
    build_auth_provider,
)


@pytest.mark.asyncio
async def test_pat_auth_provider_returns_basic_header() -> None:
    provider = PatAuthProvider("my-test-pat")
    headers = await provider.get_auth_headers()
    expected = base64.b64encode(b":my-test-pat").decode()
    assert headers == {"Authorization": f"Basic {expected}"}


@pytest.mark.asyncio
async def test_sp_auth_provider_returns_bearer_header() -> None:
    mock_manager = AsyncMock(spec=ServicePrincipalTokenManager)
    mock_manager.get_token.return_value = "fake-bearer-token"
    provider = ServicePrincipalAuthProvider(mock_manager)
    headers = await provider.get_auth_headers()
    assert headers == {"Authorization": "Bearer fake-bearer-token"}
    mock_manager.get_token.assert_called_once()


@pytest.mark.asyncio
async def test_token_manager_caches_token() -> None:
    manager = ServicePrincipalTokenManager("cid", "csecret", "tid")
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    with patch.object(
        manager, "_fetch_token", return_value=("cached-token", future)
    ) as mock_fetch:
        token1 = await manager.get_token()
        token2 = await manager.get_token()
        assert token1 == "cached-token"
        assert token2 == "cached-token"
        mock_fetch.assert_called_once()


@pytest.mark.asyncio
async def test_token_manager_refreshes_expired_token() -> None:
    manager = ServicePrincipalTokenManager("cid", "csecret", "tid")
    expired = datetime.now(timezone.utc) + timedelta(minutes=2)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    with patch.object(
        manager,
        "_fetch_token",
        side_effect=[("first-token", expired), ("second-token", future)],
    ) as mock_fetch:
        token1 = await manager.get_token()
        assert token1 == "first-token"
        token2 = await manager.get_token()
        assert token2 == "second-token"
        assert mock_fetch.call_count == 2


@pytest.mark.asyncio
async def test_token_manager_concurrent_access() -> None:
    manager = ServicePrincipalTokenManager("cid", "csecret", "tid")
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    call_count = 0

    async def slow_fetch() -> tuple[str, datetime]:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return ("concurrent-token", future)

    with patch.object(manager, "_fetch_token", side_effect=slow_fetch):
        tokens = await asyncio.gather(*[manager.get_token() for _ in range(10)])
        assert all(t == "concurrent-token" for t in tokens)
        assert call_count == 1


@pytest.mark.asyncio
async def test_fetch_token_posts_to_azure_ad() -> None:
    manager = ServicePrincipalTokenManager("my-client-id", "my-secret", "my-tenant")
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "returned-token",
        "expires_in": 3600,
    }
    mock_response.raise_for_status = MagicMock()

    with patch("azure_devops.client.auth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        token, expires_at = await manager._fetch_token()

        assert token == "returned-token"
        assert expires_at > datetime.now(timezone.utc)
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "my-tenant" in call_args[0][0]
        assert call_args[1]["data"]["grant_type"] == "client_credentials"
        assert call_args[1]["data"]["client_id"] == "my-client-id"
        assert call_args[1]["data"]["client_secret"] == "my-secret"
        assert call_args[1]["data"]["scope"] == ADO_SCOPE


@pytest.mark.asyncio
async def test_fetch_token_handles_error() -> None:
    manager = ServicePrincipalTokenManager("cid", "csecret", "tid")
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 401
    mock_response.text = "invalid_client"

    import httpx

    with patch("azure_devops.client.auth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_response
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await manager._fetch_token()


def test_build_auth_provider_pat_mode() -> None:
    import azure_devops.client.auth as auth_module

    auth_module._token_manager = None
    provider = build_auth_provider({"personal_access_token": "my-pat"})
    assert isinstance(provider, PatAuthProvider)


def test_build_auth_provider_sp_mode() -> None:
    import azure_devops.client.auth as auth_module

    auth_module._token_manager = None
    provider = build_auth_provider(
        {
            "client_id": "cid",
            "client_secret": "csecret",
            "tenant_id": "tid",
        }
    )
    assert isinstance(provider, ServicePrincipalAuthProvider)


def test_build_auth_provider_no_credentials() -> None:
    import azure_devops.client.auth as auth_module

    auth_module._token_manager = None
    with pytest.raises(ValueError, match="No authentication configured"):
        build_auth_provider({})


def test_build_auth_provider_both_credentials() -> None:
    import azure_devops.client.auth as auth_module

    auth_module._token_manager = None
    with pytest.raises(ValueError, match="Both PAT and Service Principal"):
        build_auth_provider(
            {
                "personal_access_token": "pat",
                "client_id": "cid",
                "client_secret": "csecret",
                "tenant_id": "tid",
            }
        )


def test_build_auth_provider_partial_sp() -> None:
    import azure_devops.client.auth as auth_module

    auth_module._token_manager = None
    with pytest.raises(ValueError, match="client_secret"):
        build_auth_provider({"client_id": "cid"})
