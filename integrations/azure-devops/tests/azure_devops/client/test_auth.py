"""Tests for :mod:`azure_devops.client.auth`.

Covered behavior:
- ``PersonalAccessTokenAuthenticator.apply`` sets ``httpx.BasicAuth("", pat)`` on the client.
- ``ServicePrincipalAuthenticator._fetch_token`` posts form-encoded
  client-credentials to the Entra ID token endpoint with the
  Azure DevOps resource scope.
- The cached token is reused while valid and refreshed once expired.
- Concurrent ``_get_valid_token`` calls only fetch once (asyncio.Lock).
- ``apply`` writes ``Authorization: Bearer <token>`` and clears ``client.auth``.
- ``EntraIdToken.is_expired`` applies the 2-minute safety buffer.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import AsyncClient, BasicAuth

from azure_devops.client.auth import (
    AZURE_DEVOPS_DEFAULT_SCOPE,
    EntraIdToken,
    PersonalAccessTokenAuthenticator,
    ServicePrincipalAuthenticator,
)


class TestPersonalAccessTokenAuthenticator:
    @pytest.mark.asyncio
    async def test_apply_sets_basic_auth(self) -> None:
        authenticator = PersonalAccessTokenAuthenticator("my-pat-value")
        client = AsyncClient()
        try:
            await authenticator.apply(client)
            assert isinstance(client.auth, BasicAuth)
            # httpx BasicAuth stores the encoded header on _auth_header.
            assert (
                client.auth._auth_header == BasicAuth("", "my-pat-value")._auth_header
            )
        finally:
            await client.aclose()


class TestEntraIdToken:
    def test_fresh_token_is_not_expired(self) -> None:
        token = EntraIdToken(access_token="a", expires_in=3600)
        assert not token.is_expired

    def test_old_token_is_expired(self) -> None:
        token = EntraIdToken(access_token="a", expires_in=3600)
        token._created_at = datetime.now(timezone.utc) - timedelta(hours=2)
        assert token.is_expired

    def test_buffer_marks_token_expired_just_before_real_expiry(self) -> None:
        """The 2-minute safety buffer should mark a token as expired
        ~119s before its real ``expires_in`` deadline."""
        token = EntraIdToken(access_token="a", expires_in=60)
        # 60s lifetime < 120s buffer → immediately considered expired.
        assert token.is_expired


class TestServicePrincipalAuthenticator:
    def _build(self) -> ServicePrincipalAuthenticator:
        return ServicePrincipalAuthenticator(
            tenant_id="tenant-id",
            client_id="client-id",
            client_secret="client-secret",
        )

    def test_token_url_uses_tenant(self) -> None:
        auth = self._build()
        assert (
            auth._token_url
            == "https://login.microsoftonline.com/tenant-id/oauth2/v2.0/token"
        )

    @pytest.mark.asyncio
    async def test_fetch_token_posts_client_credentials(self) -> None:
        auth = self._build()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "fresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        token = await auth._fetch_token(mock_client)

        assert token.access_token == "fresh-token"
        assert token.expires_in == 3600
        assert token.token_type == "Bearer"

        mock_client.post.assert_awaited_once()
        await_args = mock_client.post.await_args
        assert await_args is not None
        call_kwargs = await_args.kwargs
        call_args = await_args.args
        assert call_args[0] == auth._token_url
        assert call_kwargs["data"] == {
            "grant_type": "client_credentials",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "scope": AZURE_DEVOPS_DEFAULT_SCOPE,
        }
        assert (
            call_kwargs["headers"]["Content-Type"]
            == "application/x-www-form-urlencoded"
        )

    @pytest.mark.asyncio
    async def test_fetch_token_raises_on_http_error(self) -> None:
        auth = self._build()

        error_response = MagicMock()
        error_response.status_code = 401
        error_response.text = "invalid_client"
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=error_response
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=error_response)

        with pytest.raises(httpx.HTTPStatusError):
            await auth._fetch_token(mock_client)

    @pytest.mark.asyncio
    async def test_cached_token_reused_within_expiry(self) -> None:
        auth = self._build()
        cached = EntraIdToken(access_token="cached-token", expires_in=3600)
        auth._cached_token = cached

        fetch_mock = AsyncMock(
            return_value=EntraIdToken(access_token="should-not-appear", expires_in=3600)
        )
        auth._fetch_token = fetch_mock  # type: ignore[method-assign]

        client = AsyncMock()
        result = await auth._get_valid_token(client)

        assert result is cached
        fetch_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_expired_token_triggers_refresh(self) -> None:
        auth = self._build()
        expired = EntraIdToken(access_token="old-token", expires_in=3600)
        expired._created_at = datetime.now(timezone.utc) - timedelta(hours=2)
        auth._cached_token = expired

        fresh = EntraIdToken(access_token="new-token", expires_in=3600)
        fetch_mock = AsyncMock(return_value=fresh)
        auth._fetch_token = fetch_mock  # type: ignore[method-assign]

        client = AsyncMock()
        result = await auth._get_valid_token(client)

        assert result is fresh
        assert auth._cached_token is fresh
        fetch_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_concurrent_refresh_fetches_token_once(self) -> None:
        """Five concurrent callers racing into an empty cache should
        trigger exactly one ``_fetch_token`` call thanks to the lock."""
        auth = self._build()
        call_count = 0

        async def fake_fetch(client: AsyncClient) -> EntraIdToken:
            nonlocal call_count
            call_count += 1
            # Yield the event loop so all waiters queue on the lock before
            # the first fetcher finishes.
            await asyncio.sleep(0)
            return EntraIdToken(
                access_token=f"token-{call_count}",
                expires_in=3600,
            )

        auth._fetch_token = fake_fetch  # type: ignore[method-assign]

        client = AsyncMock()
        results = await asyncio.gather(
            *(auth._get_valid_token(client) for _ in range(5))
        )

        assert call_count == 1
        assert all(t.access_token == "token-1" for t in results)

    @pytest.mark.asyncio
    async def test_apply_sets_bearer_header_and_clears_auth(self) -> None:
        auth = self._build()
        auth._cached_token = EntraIdToken(
            access_token="bearer-value",
            expires_in=3600,
            token_type="Bearer",
        )

        client = AsyncClient()
        # Pre-seed a BasicAuth so we can verify ``apply`` clears it, which is
        # important because httpx would otherwise override our Bearer header.
        client.auth = BasicAuth("", "stale-pat")
        try:
            await auth.apply(client)
            assert client.auth is None
            assert client.headers["Authorization"] == "Bearer bearer-value"
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_apply_fetches_token_when_cache_empty(self) -> None:
        auth = self._build()
        fetched = EntraIdToken(access_token="fetched-on-demand", expires_in=3600)
        fetch_mock = AsyncMock(return_value=fetched)
        auth._fetch_token = fetch_mock  # type: ignore[method-assign]

        client = AsyncClient()
        try:
            await auth.apply(client)
            assert client.headers["Authorization"] == "Bearer fetched-on-demand"
            fetch_mock.assert_awaited_once()
        finally:
            await client.aclose()
