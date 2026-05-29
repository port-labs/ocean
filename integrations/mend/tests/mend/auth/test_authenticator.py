import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mend.auth.authenticator import MendAuthenticator
from mend.exceptions import MendAuthenticationError


@pytest.fixture
def authenticator() -> MendAuthenticator:
    return MendAuthenticator(
        base_url="https://api-saas.mend.io",
        email="test@example.com",
        user_key="test-user-key",
        org_uuid="test-org-uuid",
    )


class TestMendAuthenticator:
    def test_is_token_expired_no_expiry(self, authenticator: MendAuthenticator) -> None:
        authenticator._token_expires_at = None
        assert authenticator.is_token_expired is True

    def test_is_token_expired_future(self, authenticator: MendAuthenticator) -> None:
        authenticator._token_expires_at = time.time() + 3600
        assert authenticator.is_token_expired is False

    def test_is_token_expired_past(self, authenticator: MendAuthenticator) -> None:
        authenticator._token_expires_at = time.time() - 10
        assert authenticator.is_token_expired is True

    @pytest.mark.asyncio
    async def test_fetch_refresh_token_success(
        self, authenticator: MendAuthenticator
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": {"refreshToken": "test-refresh-token"}
        }
        mock_response.raise_for_status.return_value = None

        with patch("mend.auth.authenticator.http_async_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            token = await authenticator._fetch_refresh_token()
            assert token == "test-refresh-token"

    @pytest.mark.asyncio
    async def test_fetch_refresh_token_http_error(
        self, authenticator: MendAuthenticator
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_response
        )

        with patch("mend.auth.authenticator.http_async_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            with pytest.raises(MendAuthenticationError):
                await authenticator._fetch_refresh_token()

    @pytest.mark.asyncio
    async def test_fetch_jwt_token_success(
        self, authenticator: MendAuthenticator
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": {"jwtToken": "test-jwt", "tokenTTL": 1800}
        }
        mock_response.raise_for_status.return_value = None

        with patch("mend.auth.authenticator.http_async_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            jwt, ttl = await authenticator._fetch_jwt_token("refresh-token")
            assert jwt == "test-jwt"
            assert ttl == 1800

    @pytest.mark.asyncio
    async def test_fetch_jwt_token_defaults_ttl(
        self, authenticator: MendAuthenticator
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": {"jwtToken": "test-jwt"}}
        mock_response.raise_for_status.return_value = None

        with patch("mend.auth.authenticator.http_async_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            _, ttl = await authenticator._fetch_jwt_token("refresh-token")
            assert ttl == 3600

    @pytest.mark.asyncio
    async def test_fetch_refresh_token_missing_response_object(
        self, authenticator: MendAuthenticator
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"unexpected": "shape"}
        mock_response.raise_for_status.return_value = None

        with patch("mend.auth.authenticator.http_async_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            with pytest.raises(MendAuthenticationError, match="missing 'response'"):
                await authenticator._fetch_refresh_token()

    @pytest.mark.asyncio
    async def test_fetch_refresh_token_missing_refresh_token(
        self, authenticator: MendAuthenticator
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": {"refreshToken": ""}}
        mock_response.raise_for_status.return_value = None

        with patch("mend.auth.authenticator.http_async_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            with pytest.raises(MendAuthenticationError, match="refreshToken"):
                await authenticator._fetch_refresh_token()

    @pytest.mark.asyncio
    async def test_fetch_refresh_token_non_object_body(
        self, authenticator: MendAuthenticator
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = ["not", "an", "object"]
        mock_response.raise_for_status.return_value = None

        with patch("mend.auth.authenticator.http_async_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            with pytest.raises(MendAuthenticationError, match="not a JSON object"):
                await authenticator._fetch_refresh_token()

    @pytest.mark.asyncio
    async def test_fetch_refresh_token_invalid_json(
        self, authenticator: MendAuthenticator
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("invalid JSON")
        mock_response.raise_for_status.return_value = None

        with patch("mend.auth.authenticator.http_async_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            with pytest.raises(MendAuthenticationError, match="Failed to parse"):
                await authenticator._fetch_refresh_token()

    @pytest.mark.asyncio
    async def test_fetch_jwt_token_missing_jwt_token(
        self, authenticator: MendAuthenticator
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": {"tokenTTL": 1800}}
        mock_response.raise_for_status.return_value = None

        with patch("mend.auth.authenticator.http_async_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            with pytest.raises(MendAuthenticationError, match="jwtToken"):
                await authenticator._fetch_jwt_token("refresh-token")

    @pytest.mark.asyncio
    async def test_fetch_jwt_token_non_numeric_ttl(
        self, authenticator: MendAuthenticator
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": {"jwtToken": "test-jwt", "tokenTTL": "not-a-number"}
        }
        mock_response.raise_for_status.return_value = None

        with patch("mend.auth.authenticator.http_async_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            with pytest.raises(MendAuthenticationError, match="Failed to parse"):
                await authenticator._fetch_jwt_token("refresh-token")

    @pytest.mark.asyncio
    async def test_authenticate_full_flow(
        self, authenticator: MendAuthenticator
    ) -> None:
        with (
            patch.object(
                authenticator, "_fetch_refresh_token", AsyncMock(return_value="ref-tok")
            ),
            patch.object(
                authenticator,
                "_fetch_jwt_token",
                AsyncMock(return_value=("jwt-tok", 1800)),
            ),
        ):
            await authenticator._authenticate()
            assert authenticator._jwt_token == "jwt-tok"
            assert authenticator._token_expires_at is not None

    @pytest.mark.asyncio
    async def test_get_auth_headers_uses_in_memory_token(
        self, authenticator: MendAuthenticator
    ) -> None:
        authenticator._jwt_token = "cached-jwt"
        authenticator._token_expires_at = time.time() + 3600

        headers = await authenticator.get_auth_headers()
        assert headers["Authorization"] == "Bearer cached-jwt"

    @pytest.mark.asyncio
    async def test_get_auth_headers_refreshes_expired_token(
        self, authenticator: MendAuthenticator
    ) -> None:
        authenticator._jwt_token = None
        authenticator._token_expires_at = None

        async def fake_authenticate() -> None:
            authenticator._jwt_token = "new-jwt"
            authenticator._token_expires_at = time.time() + 3600

        with patch.object(
            authenticator, "_authenticate", AsyncMock(side_effect=fake_authenticate)
        ):
            headers = await authenticator.get_auth_headers()
            assert headers["Authorization"] == "Bearer new-jwt"

    @pytest.mark.asyncio
    async def test_invalidate_token_clears_in_memory_state(
        self, authenticator: MendAuthenticator
    ) -> None:
        authenticator._jwt_token = "some-jwt"
        authenticator._token_expires_at = time.time() + 3600

        await authenticator.invalidate_token()

        assert authenticator._jwt_token is None
        assert authenticator._token_expires_at is None
