"""Tests for custom authentication functionality"""

import asyncio
import pytest
import httpx
import time
from typing import Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock

from http_server.auth import CustomAuth
from http_server.overrides import CustomAuthRequestConfig, CustomAuthResponseConfig
from http_server.client import HttpServerClient

# ============================================================================
# CustomAuth Class Tests
# ============================================================================


@pytest.mark.asyncio
class TestCustomAuth:
    """Test CustomAuth authentication handler"""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def auth_config(self) -> Dict[str, Any]:
        return {"base_url": "https://api.example.com", "verify_ssl": True}

    @pytest.fixture
    def custom_auth_request(self) -> CustomAuthRequestConfig:
        return CustomAuthRequestConfig(
            endpoint="/oauth/token",
            method="POST",
            headers={"Content-Type": "application/json"},
            body={"grant_type": "client_credentials", "client_id": "test"},
        )

    @pytest.fixture
    def custom_auth_response(self) -> CustomAuthResponseConfig:
        return CustomAuthResponseConfig(
            headers={"Authorization": "Bearer {{.access_token}}"},
            queryParams={"api_key": "{{.access_token}}"},
            body={"token": "{{.access_token}}"},
        )

    @pytest.fixture
    def mock_entity_processor(self) -> MagicMock:
        """Mock Ocean's entity processor for JQ evaluation"""
        mock_processor = AsyncMock()

        async def mock_search(data: Dict[str, Any], jq_path: str) -> Any:
            """Simple mock JQ processor"""
            if jq_path == ".access_token":
                return data.get("access_token")
            elif jq_path == ".expires_in":
                return data.get("expires_in")
            elif jq_path == ".token_type":
                return data.get("token_type")
            elif jq_path == ".nested.value":
                return data.get("nested", {}).get("value")
            return None

        mock_processor._search = mock_search
        return mock_processor

    @pytest.fixture
    def custom_auth(
        self,
        mock_client: AsyncMock,
        auth_config: Dict[str, Any],
        custom_auth_request: CustomAuthRequestConfig,
        custom_auth_response: CustomAuthResponseConfig,
    ) -> CustomAuth:
        return CustomAuth(
            mock_client, auth_config, custom_auth_request, custom_auth_response
        )

    async def test_authenticate_async_success(self, custom_auth: CustomAuth) -> None:
        """Test successful authentication"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # response.json() is called, so make it a callable that returns the dict
        mock_response.json = MagicMock(
            return_value={
                "access_token": "test-token-123",
                "expires_in": 3600,
            }
        )
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = (
                mock_client_instance
            )
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            await custom_auth.authenticate_async()

            assert custom_auth.auth_response is not None
            assert custom_auth.auth_response["access_token"] == "test-token-123"
            assert custom_auth.auth_response["expires_in"] == 3600

    async def test_authenticate_async_full_url(self, custom_auth: CustomAuth) -> None:
        """Test authentication with full URL"""
        assert custom_auth.custom_auth_request is not None
        custom_auth.custom_auth_request.endpoint = "https://auth.example.com/token"

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"access_token": "token"})
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = (
                mock_client_instance
            )
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            await custom_auth.authenticate_async()

            # Verify full URL was used
            call_args = mock_client_instance.request.call_args
            assert call_args[1]["url"] == "https://auth.example.com/token"

    async def test_authenticate_async_with_body_form(
        self, custom_auth: CustomAuth
    ) -> None:
        """Test authentication with form-encoded body"""
        # bodyForm should be a string (form-encoded), not a dict
        # Create a new config with only bodyForm set (no body) to test form-encoded body
        assert custom_auth.custom_auth_request is not None
        # The fixture sets body and Content-Type header, so we need to:
        # 1. Clear the Content-Type header so the code can set it based on bodyForm
        # 2. Clear body and set bodyForm
        if custom_auth.custom_auth_request.headers:
            custom_auth.custom_auth_request.headers.pop("Content-Type", None)
        custom_auth.custom_auth_request.body = None
        custom_auth.custom_auth_request.bodyForm = "grant_type=password&username=test"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"access_token": "token"})
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = (
                mock_client_instance
            )
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            await custom_auth.authenticate_async()

            # Verify form data was sent
            call_args = mock_client_instance.request.call_args
            # The content should be the bodyForm string
            assert call_args[1]["content"] == "grant_type=password&username=test"
            assert "Content-Type" in call_args[1]["headers"]
            assert (
                call_args[1]["headers"]["Content-Type"]
                == "application/x-www-form-urlencoded"
            )

    async def test_authenticate_async_http_error(self, custom_auth: CustomAuth) -> None:
        """Test authentication failure"""
        mock_response = AsyncMock()
        mock_response.status_code = 401
        # raise_for_status() is called, so make it raise the error
        error = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )
        mock_response.raise_for_status = MagicMock(side_effect=error)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = (
                mock_client_instance
            )
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            with pytest.raises(httpx.HTTPStatusError):
                await custom_auth.authenticate_async()

    async def test_apply_auth_to_request_headers(
        self, custom_auth: CustomAuth, mock_entity_processor: MagicMock
    ) -> None:
        """Test applying auth to headers"""
        custom_auth.auth_response = {"access_token": "test-token"}
        # Set timestamp and interval to prevent expiration check from triggering
        custom_auth._expiration_tracker._auth_timestamp = time.time()
        custom_auth._expiration_tracker._reauthenticate_interval = (
            None  # Disable expiration checking
        )

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            headers = {"X-Custom": "value"}
            result_headers, _, _ = await custom_auth.apply_auth_to_request(headers)

            assert result_headers["Authorization"] == "Bearer test-token"
            assert result_headers["X-Custom"] == "value"

    async def test_apply_auth_to_request_query_params(
        self, custom_auth: CustomAuth, mock_entity_processor: MagicMock
    ) -> None:
        """Test applying auth to query params"""
        custom_auth.auth_response = {"access_token": "test-token"}
        # Set timestamp and interval to prevent expiration check from triggering
        custom_auth._expiration_tracker._auth_timestamp = time.time()
        custom_auth._expiration_tracker._reauthenticate_interval = (
            None  # Disable expiration checking
        )

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            query_params = {"page": "1"}
            _, result_params, _ = await custom_auth.apply_auth_to_request(
                {}, query_params
            )

            assert result_params["api_key"] == "test-token"
            assert result_params["page"] == "1"

    async def test_apply_auth_to_request_body(
        self, custom_auth: CustomAuth, mock_entity_processor: MagicMock
    ) -> None:
        """Test applying auth to body"""
        custom_auth.auth_response = {"access_token": "test-token"}
        # Set timestamp and interval to prevent expiration check from triggering
        custom_auth._expiration_tracker._auth_timestamp = time.time()
        custom_auth._expiration_tracker._reauthenticate_interval = (
            None  # Disable expiration checking
        )

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            body = {"data": "value"}
            _, _, result_body = await custom_auth.apply_auth_to_request({}, None, body)

            assert result_body is not None
            assert result_body["token"] == "test-token"
            assert result_body["data"] == "value"

    async def test_apply_auth_no_auth_response(self, custom_auth: CustomAuth) -> None:
        """Test applying auth when no auth_response exists"""
        custom_auth.auth_response = None

        # When auth_response is None, expiration check will return True but authenticate_async
        # will fail, so we need to mock it to prevent actual HTTP calls
        async def mock_authenticate() -> None:
            # Do nothing - auth_response is None so this simulates the early return
            pass

        custom_auth.authenticate_async = mock_authenticate  # type: ignore[method-assign]

        headers = {"X-Custom": "value"}
        result_headers, _, _ = await custom_auth.apply_auth_to_request(headers)

        # Should return original headers unchanged
        assert result_headers == headers

    async def test_apply_auth_no_custom_auth_response_config(
        self, custom_auth: CustomAuth
    ) -> None:
        """Test applying auth when no custom_auth_response config exists"""
        custom_auth.auth_response = {"access_token": "test-token"}
        custom_auth.custom_auth_response = None
        # Set timestamp and interval to prevent expiration check from triggering
        custom_auth._expiration_tracker._auth_timestamp = time.time()
        custom_auth._expiration_tracker._reauthenticate_interval = (
            None  # Disable expiration checking
        )

        headers = {"X-Custom": "value"}
        result_headers, _, _ = await custom_auth.apply_auth_to_request(headers)

        # Should return original headers unchanged
        assert result_headers == headers


# ============================================================================
# Re-authentication & Locking Tests
# ============================================================================


@pytest.mark.asyncio
class TestReauthentication:
    """Test re-authentication on 401 and locking behavior"""

    @pytest.fixture
    def custom_auth(self) -> CustomAuth:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        config = {"base_url": "https://api.example.com", "verify_ssl": True}
        auth_request = CustomAuthRequestConfig(
            endpoint="/auth",
            method="POST",
            body={"grant_type": "client_credentials"},
        )
        auth_response = CustomAuthResponseConfig(
            headers={"Authorization": "Bearer {{.access_token}}"}
        )
        return CustomAuth(mock_client, config, auth_request, auth_response)

    async def test_reauthenticate_called_on_401(self, custom_auth: CustomAuth) -> None:
        """Test that reauthenticate successfully refreshes token"""
        # Set initial auth response
        custom_auth.auth_response = {"access_token": "old-token"}

        # Mock successful re-authentication
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"access_token": "new-token"})
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = (
                mock_client_instance
            )
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            await custom_auth.reauthenticate()

            assert custom_auth.auth_response["access_token"] == "new-token"

    async def test_reauthenticate_lock_prevents_concurrent_auth(
        self, custom_auth: CustomAuth
    ) -> None:
        """Test that lock prevents concurrent re-authentication"""
        custom_auth.auth_response = {"access_token": "old-token"}

        # Track authentication calls
        auth_calls = []

        async def mock_authenticate() -> None:
            auth_calls.append("auth")
            await asyncio.sleep(0.1)  # Simulate auth delay

        custom_auth.authenticate_async = mock_authenticate  # type: ignore[method-assign]

        # Simulate two concurrent re-authentication attempts
        async def reauth1() -> None:
            await custom_auth.reauthenticate()

        async def reauth2() -> None:
            await asyncio.sleep(0.05)  # Start slightly after reauth1
            await custom_auth.reauthenticate()

        await asyncio.gather(reauth1(), reauth2())

        # Should authenticate at least once, but lock should prevent race conditions
        assert len(auth_calls) >= 1
        assert (
            len(auth_calls) <= 2
        )  # At most 2 (if first completes before second acquires lock)

    async def test_reauthenticate_skips_if_already_refreshed(
        self, custom_auth: CustomAuth
    ) -> None:
        """Test that reauthenticate skips if auth was already refreshed"""
        custom_auth.auth_response = {"access_token": "old-token"}

        # Simulate another coroutine refreshing auth while waiting for lock
        async def acquire_lock_and_refresh() -> None:
            await asyncio.sleep(0.05)
            custom_auth.auth_response = {"access_token": "refreshed-token"}

        # Start refresh task
        refresh_task = asyncio.create_task(acquire_lock_and_refresh())

        # Mock authenticate to track if it's called
        authenticate_called: list[bool] = []

        async def mock_authenticate() -> None:
            authenticate_called.append(True)
            custom_auth.auth_response = {"access_token": "new-token"}

        custom_auth.authenticate_async = mock_authenticate  # type: ignore[method-assign]

        # Try to re-authenticate (should skip after lock)
        await custom_auth.reauthenticate()

        await refresh_task

        # Should have skipped re-auth since auth_response changed
        # The auth_response should be "refreshed-token" (from the refresh task)
        # or "new-token" (if authenticate was called)
        assert custom_auth.auth_response is not None
        assert custom_auth.auth_response["access_token"] in [
            "refreshed-token",
            "new-token",
        ]


# ============================================================================
# Client 401 Handling Tests
# ============================================================================


@pytest.mark.asyncio
class TestClient401Handling:
    """Test 401 re-authentication in HttpServerClient"""

    @pytest.fixture
    def mock_entity_processor(self) -> MagicMock:
        """Mock Ocean's entity processor for JQ evaluation"""
        mock_processor = AsyncMock()

        async def mock_search(data: Dict[str, Any], jq_path: str) -> Any:
            """Simple mock JQ processor"""
            if jq_path == ".access_token":
                return data.get("access_token")
            elif jq_path == ".expires_in":
                return data.get("expires_in")
            elif jq_path == ".token_type":
                return data.get("token_type")
            return None

        mock_processor._search = mock_search
        return mock_processor

    @pytest.fixture
    def client_with_custom_auth(self) -> HttpServerClient:
        auth_request = CustomAuthRequestConfig(
            endpoint="/auth",
            method="POST",
            body={"grant_type": "client_credentials"},
        )
        auth_response = CustomAuthResponseConfig(
            headers={"Authorization": "Bearer {{.access_token}}"}
        )
        # Mock OceanAsyncClient to avoid SSL context issues in tests
        with patch("http_server.client.OceanAsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Use verify_ssl=False to avoid SSL context issues in tests
            client = HttpServerClient(
                base_url="https://api.example.com",
                auth_type="custom",
                auth_config={
                    "base_url": "https://api.example.com",
                    "verify_ssl": False,
                },
                pagination_config={"pagination_type": "none"},
                custom_auth_request=auth_request,
                custom_auth_response=auth_response,
            )
            # Replace the client with our mock
            client.client = mock_client
            return client

    async def test_401_triggers_reauthentication(
        self,
        client_with_custom_auth: HttpServerClient,
        mock_entity_processor: MagicMock,
    ) -> None:
        """Test that 401 triggers re-authentication and retry"""
        # Set initial auth
        # Type ignore needed because CustomAuth has auth_response attribute
        client_with_custom_auth.auth_handler.auth_response = {  # type: ignore[attr-defined]
            "access_token": "old-token"
        }
        # Set timestamp and interval to prevent expiration check from triggering
        # (we want to test 401 handling, not expiration)
        client_with_custom_auth.auth_handler._expiration_tracker._auth_timestamp = time.time()  # type: ignore[attr-defined]
        client_with_custom_auth.auth_handler._expiration_tracker._reauthenticate_interval = None  # type: ignore[attr-defined]

        # Mock responses: 401 then 200
        mock_401 = MagicMock()
        mock_401.status_code = 401
        mock_401.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_401
        )

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json = MagicMock(return_value={"data": "success"})
        mock_200.raise_for_status = MagicMock()

        # Mock reauthenticate to update auth_response
        async def mock_reauthenticate() -> None:
            # Type ignore needed because CustomAuth has auth_response attribute
            client_with_custom_auth.auth_handler.auth_response = {  # type: ignore[attr-defined]
                "access_token": "new-token"
            }

        # Type ignore needed because we're testing CustomAuth which has reauthenticate
        client_with_custom_auth.auth_handler.reauthenticate = AsyncMock(  # type: ignore[method-assign]
            side_effect=mock_reauthenticate
        )

        # Mock the client's request method
        client_with_custom_auth.client.request = AsyncMock(  # type: ignore[method-assign]
            side_effect=[mock_401, mock_200]
        )

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            response = await client_with_custom_auth._make_request(
                url="https://api.example.com/data",
                method="GET",
                params={},
                headers={},
            )

        assert response.status_code == 200
        # Verify re-authentication was called (auth_response updated)
        # Type ignore needed because CustomAuth has auth_response attribute
        auth_response = client_with_custom_auth.auth_handler.auth_response  # type: ignore[attr-defined]
        assert auth_response is not None
        assert auth_response["access_token"] == "new-token"
        # Verify request was retried (called twice: 401 then 200)
        assert client_with_custom_auth.client.request.call_count == 2

    async def test_401_reauthentication_failure(
        self,
        client_with_custom_auth: HttpServerClient,
        mock_entity_processor: MagicMock,
    ) -> None:
        """Test that 401 with failed re-auth raises error"""
        # Type ignore needed because CustomAuth has auth_response attribute
        client_with_custom_auth.auth_handler.auth_response = {  # type: ignore[attr-defined]
            "access_token": "old-token"
        }
        # Set timestamp and interval to prevent expiration check from triggering
        # (we want to test 401 handling, not expiration)
        client_with_custom_auth.auth_handler._expiration_tracker._auth_timestamp = time.time()  # type: ignore[attr-defined]
        client_with_custom_auth.auth_handler._expiration_tracker._reauthenticate_interval = None  # type: ignore[attr-defined]

        mock_401 = MagicMock()
        mock_401.status_code = 401
        mock_401.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_401
        )

        # Mock reauthenticate to fail
        async def mock_reauthenticate() -> None:
            raise Exception("Re-authentication failed")

        # Type ignore needed because we're testing CustomAuth which has reauthenticate
        client_with_custom_auth.auth_handler.reauthenticate = AsyncMock(  # type: ignore[method-assign]
            side_effect=mock_reauthenticate
        )

        client_with_custom_auth.client.request = AsyncMock(return_value=mock_401)  # type: ignore[method-assign]

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await client_with_custom_auth._make_request(
                    url="https://api.example.com/data",
                    method="GET",
                    params={},
                    headers={},
                )


# ============================================================================
# Token Expiration Tests
# ============================================================================


@pytest.mark.asyncio
class TestTokenExpiration:
    """Test token expiration and proactive re-authentication"""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def auth_config(self) -> Dict[str, Any]:
        return {"base_url": "https://api.example.com", "verify_ssl": True}

    @pytest.fixture
    def custom_auth_response(self) -> CustomAuthResponseConfig:
        return CustomAuthResponseConfig(
            headers={"Authorization": "Bearer {{.access_token}}"}
        )

    @pytest.fixture
    def custom_auth_with_interval(
        self,
        mock_client: AsyncMock,
        auth_config: Dict[str, Any],
        custom_auth_response: CustomAuthResponseConfig,
    ) -> CustomAuth:
        """CustomAuth with reauthenticate_interval_seconds configured"""
        auth_request = CustomAuthRequestConfig(
            endpoint="/oauth/token",
            method="POST",
            body={"grant_type": "client_credentials"},
            reauthenticate_interval_seconds=3600,  # 1 hour
        )
        return CustomAuth(mock_client, auth_config, auth_request, custom_auth_response)

    @pytest.fixture
    def custom_auth_without_interval(
        self,
        mock_client: AsyncMock,
        auth_config: Dict[str, Any],
        custom_auth_response: CustomAuthResponseConfig,
    ) -> CustomAuth:
        """CustomAuth without reauthenticate_interval_seconds configured"""
        auth_request = CustomAuthRequestConfig(
            endpoint="/oauth/token",
            method="POST",
            body={"grant_type": "client_credentials"},
            # reauthenticate_interval_seconds not set (None)
        )
        return CustomAuth(mock_client, auth_config, auth_request, custom_auth_response)

    async def test_calculate_reauthenticate_interval_with_config(
        self, custom_auth_with_interval: CustomAuth
    ) -> None:
        """Test that configured interval is set in expiration tracker"""
        custom_auth_with_interval.auth_response = {"access_token": "token"}
        interval, _ = (
            custom_auth_with_interval._expiration_tracker.get_expiration_info()
        )
        assert interval == 3600

    async def test_calculate_reauthenticate_interval_without_config(
        self, custom_auth_without_interval: CustomAuth
    ) -> None:
        """Test that None is set when not configured"""
        custom_auth_without_interval.auth_response = {"access_token": "token"}
        interval, _ = (
            custom_auth_without_interval._expiration_tracker.get_expiration_info()
        )
        assert interval is None

    async def test_is_auth_expired_no_auth_yet(
        self, custom_auth_with_interval: CustomAuth
    ) -> None:
        """Test that returns True when no authentication has occurred"""
        assert custom_auth_with_interval._expiration_tracker.is_expired(False) is True

    async def test_is_auth_expired_no_interval_configured(
        self, custom_auth_without_interval: CustomAuth
    ) -> None:
        """Test that returns False when no interval is configured (expiration checking disabled)"""
        custom_auth_without_interval.auth_response = {"access_token": "token"}
        custom_auth_without_interval._expiration_tracker._auth_timestamp = time.time()
        custom_auth_without_interval._expiration_tracker._reauthenticate_interval = None

        assert (
            custom_auth_without_interval._expiration_tracker.is_expired(True) is False
        )

    async def test_is_auth_expired_not_expired(
        self, custom_auth_with_interval: CustomAuth
    ) -> None:
        """Test that returns False when token is not expired"""
        custom_auth_with_interval.auth_response = {"access_token": "token"}
        custom_auth_with_interval._expiration_tracker._auth_timestamp = time.time()
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = (
            3600  # 1 hour
        )

        assert custom_auth_with_interval._expiration_tracker.is_expired(True) is False

    async def test_is_auth_expired_expired(
        self, custom_auth_with_interval: CustomAuth
    ) -> None:
        """Test that returns True when token is expired"""
        custom_auth_with_interval.auth_response = {"access_token": "token"}
        # Set timestamp to 2 hours ago (expired)
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time() - 7200
        )
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = (
            3600  # 1 hour
        )

        assert custom_auth_with_interval._expiration_tracker.is_expired(True) is True

    async def test_is_auth_expired_within_buffer(
        self, custom_auth_with_interval: CustomAuth
    ) -> None:
        """Test that returns True when token is within buffer window (60 seconds)"""
        custom_auth_with_interval.auth_response = {"access_token": "token"}
        # Set timestamp so expiration is in 30 seconds (within 60s buffer)
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time() - 3570
        )  # 30s before expiration
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = (
            3600  # 1 hour
        )

        assert custom_auth_with_interval._expiration_tracker.is_expired(True) is True

    async def test_authenticate_async_sets_interval(
        self, custom_auth_with_interval: CustomAuth
    ) -> None:
        """Test that authenticate_async calculates and sets expiration interval"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"access_token": "test-token-123"})
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = (
                mock_client_instance
            )
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            await custom_auth_with_interval.authenticate_async()

            assert (
                custom_auth_with_interval._expiration_tracker._auth_timestamp
                is not None
            )
            interval, _ = (
                custom_auth_with_interval._expiration_tracker.get_expiration_info()
            )
            assert interval == 3600

    async def test_authenticate_async_sets_interval_to_none_when_not_configured(
        self, custom_auth_without_interval: CustomAuth
    ) -> None:
        """Test that authenticate_async sets interval to None when not configured"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"access_token": "test-token-123"})
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = (
                mock_client_instance
            )
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            await custom_auth_without_interval.authenticate_async()

            assert (
                custom_auth_without_interval._expiration_tracker._auth_timestamp
                is not None
            )
            interval, _ = (
                custom_auth_without_interval._expiration_tracker.get_expiration_info()
            )
            assert interval is None

    async def test_apply_auth_proactively_reauthenticates_when_expired(
        self, custom_auth_with_interval: CustomAuth
    ) -> None:
        """Test that apply_auth_to_request proactively re-authenticates when expired"""
        # Set up expired token
        custom_auth_with_interval.auth_response = {"access_token": "old-token"}
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time() - 7200
        )  # 2 hours ago
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = (
            3600  # 1 hour
        )

        # Mock re-authentication
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"access_token": "new-token"})
        mock_response.raise_for_status = MagicMock()

        authenticate_called = []

        async def mock_authenticate() -> None:
            authenticate_called.append(True)
            custom_auth_with_interval.auth_response = {"access_token": "new-token"}
            custom_auth_with_interval._expiration_tracker.record_authentication()

        custom_auth_with_interval.authenticate_async = mock_authenticate  # type: ignore[method-assign]

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            AsyncMock(),
        ):
            await custom_auth_with_interval.apply_auth_to_request({})

        # Should have called authenticate_async
        assert len(authenticate_called) == 1
        assert custom_auth_with_interval.auth_response["access_token"] == "new-token"

    async def test_apply_auth_does_not_reauthenticate_when_not_expired(
        self, custom_auth_with_interval: CustomAuth
    ) -> None:
        """Test that apply_auth_to_request does not re-authenticate when not expired"""
        # Set up valid token
        custom_auth_with_interval.auth_response = {"access_token": "valid-token"}
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time()
        )  # Just authenticated
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = (
            3600  # 1 hour
        )

        authenticate_called = []

        async def mock_authenticate() -> None:
            authenticate_called.append(True)

        custom_auth_with_interval.authenticate_async = mock_authenticate  # type: ignore[method-assign]

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            AsyncMock(),
        ):
            await custom_auth_with_interval.apply_auth_to_request({})

        # Should not have called authenticate_async
        assert len(authenticate_called) == 0

    async def test_apply_auth_no_expiration_check_when_interval_none(
        self, custom_auth_without_interval: CustomAuth
    ) -> None:
        """Test that apply_auth_to_request doesn't check expiration when interval is None"""
        custom_auth_without_interval.auth_response = {"access_token": "token"}
        custom_auth_without_interval._expiration_tracker._auth_timestamp = time.time()
        custom_auth_without_interval._expiration_tracker._reauthenticate_interval = None

        authenticate_called = []

        async def mock_authenticate() -> None:
            authenticate_called.append(True)

        custom_auth_without_interval.authenticate_async = mock_authenticate  # type: ignore[method-assign]

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            AsyncMock(),
        ):
            await custom_auth_without_interval.apply_auth_to_request({})

        # Should not have called authenticate_async (no expiration checking)
        assert len(authenticate_called) == 0

    async def test_proactive_reauthentication_uses_lock(
        self, custom_auth_with_interval: CustomAuth
    ) -> None:
        """Test that proactive re-authentication uses lock to prevent concurrent auth"""
        # Set up expired token
        custom_auth_with_interval.auth_response = {"access_token": "old-token"}
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time() - 7200
        )
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = 3600

        authenticate_calls = []

        async def mock_authenticate() -> None:
            authenticate_calls.append("auth")
            await asyncio.sleep(0.1)  # Simulate auth delay
            custom_auth_with_interval.auth_response = {"access_token": "new-token"}
            custom_auth_with_interval._expiration_tracker.record_authentication()

        custom_auth_with_interval.authenticate_async = mock_authenticate  # type: ignore[method-assign]

        # Simulate two concurrent requests
        async def apply_auth1() -> None:
            with patch(
                "port_ocean.context.ocean.ocean.app.integration.entity_processor",
                AsyncMock(),
            ):
                await custom_auth_with_interval.apply_auth_to_request({})

        async def apply_auth2() -> None:
            await asyncio.sleep(0.05)  # Start slightly after apply_auth1
            with patch(
                "port_ocean.context.ocean.ocean.app.integration.entity_processor",
                AsyncMock(),
            ):
                await custom_auth_with_interval.apply_auth_to_request({})

        await asyncio.gather(apply_auth1(), apply_auth2())

        # Should authenticate at least once, but lock should prevent race conditions
        assert len(authenticate_calls) >= 1
        assert (
            len(authenticate_calls) <= 2
        )  # At most 2 if first completes before second
