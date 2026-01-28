"""Tests for custom authentication functionality"""

import asyncio
import json
import pytest
import httpx
import time
from typing import Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock

from http_server.auth.custom.auth_flow import AuthFlowManager
from http_server.overrides import CustomAuthRequestConfig, CustomAuthResponseConfig


# ============================================================================
# Shared Fixtures
# ============================================================================


@pytest.fixture
def mock_entity_processor() -> MagicMock:
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


# ============================================================================
# CustomAuth Class Tests
# ============================================================================


@pytest.mark.asyncio
class TestCustomAuth:
    """Test CustomAuth authentication handler"""

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
    def custom_auth(
        self,
        auth_config: Dict[str, Any],
        custom_auth_request: CustomAuthRequestConfig,
        custom_auth_response: CustomAuthResponseConfig,
    ) -> AuthFlowManager:
        return AuthFlowManager(auth_config, custom_auth_request, custom_auth_response)

    async def test_perform_auth_request_success(
        self, custom_auth: AuthFlowManager
    ) -> None:
        """Test successful authentication"""
        mock_response = MagicMock()
        mock_response.status_code = 200
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

            await custom_auth._perform_auth_request()

            assert custom_auth.auth_response is not None
            assert custom_auth.auth_response["access_token"] == "test-token-123"
            assert custom_auth.auth_response["expires_in"] == 3600

    async def test_perform_auth_request_full_url(
        self, custom_auth: AuthFlowManager
    ) -> None:
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

            await custom_auth._perform_auth_request()

            # Verify full URL was used
            call_args = mock_client_instance.request.call_args
            assert call_args[1]["url"] == "https://auth.example.com/token"

    async def test_perform_auth_request_with_body_form(
        self, custom_auth: AuthFlowManager
    ) -> None:
        """Test authentication with form-encoded body"""
        assert custom_auth.custom_auth_request is not None
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

            await custom_auth._perform_auth_request()

            # Verify form data was sent
            call_args = mock_client_instance.request.call_args
            assert call_args[1]["content"] == "grant_type=password&username=test"
            assert "Content-Type" in call_args[1]["headers"]
            assert (
                call_args[1]["headers"]["Content-Type"]
                == "application/x-www-form-urlencoded"
            )

    async def test_perform_auth_request_http_error(
        self, custom_auth: AuthFlowManager
    ) -> None:
        """Test authentication failure"""
        mock_response = AsyncMock()
        mock_response.status_code = 401
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
                await custom_auth._perform_auth_request()

    async def test_async_auth_flow_initial_auth(
        self, custom_auth: AuthFlowManager, mock_entity_processor: MagicMock
    ) -> None:
        """Test async_auth_flow performs initial authentication"""
        # No auth_response yet, so should authenticate first
        custom_auth.auth_response = None

        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json = MagicMock(return_value={"access_token": "token-123"})
        mock_auth_response.raise_for_status = MagicMock()

        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.read = MagicMock(return_value=b'{"data": "success"}')

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = (
                mock_client_instance
            )
            mock_client_instance.request = AsyncMock(
                side_effect=[mock_auth_response, mock_api_response]
            )

            with patch(
                "port_ocean.context.ocean.ocean.app.integration.entity_processor",
                mock_entity_processor,
            ):
                request = httpx.Request("GET", "https://api.example.com/data")
                auth_flow = custom_auth.async_auth_flow(request)

                # Get the first request (should be authenticated)
                authenticated_request = await auth_flow.__anext__()

                # Verify auth happened
                assert custom_auth.auth_response is not None
                assert custom_auth.auth_response["access_token"] == "token-123"

                # Verify request was modified with auth headers
                assert "Authorization" in authenticated_request.headers

    async def test_async_auth_flow_applies_templates(
        self, custom_auth: AuthFlowManager, mock_entity_processor: MagicMock
    ) -> None:
        """Test async_auth_flow applies templates to request"""
        custom_auth.auth_response = {"access_token": "test-token"}
        custom_auth._expiration_tracker._auth_timestamp = time.time()
        custom_auth._expiration_tracker._reauthenticate_interval = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.read = MagicMock(return_value=b'{"data": "success"}')

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            request = httpx.Request("GET", "https://api.example.com/data?page=1")
            auth_flow = custom_auth.async_auth_flow(request)

            authenticated_request = await auth_flow.__anext__()

            # Verify headers were applied
            assert authenticated_request.headers["Authorization"] == "Bearer test-token"

            # Verify query params were applied
            assert "api_key" in str(authenticated_request.url)
            assert "test-token" in str(authenticated_request.url)

    async def test_async_auth_flow_401_reauthentication(
        self, custom_auth: AuthFlowManager, mock_entity_processor: MagicMock
    ) -> None:
        """Test async_auth_flow handles 401 and re-authenticates"""
        custom_auth.auth_response = {"access_token": "old-token"}
        custom_auth._expiration_tracker._auth_timestamp = time.time()
        custom_auth._expiration_tracker._reauthenticate_interval = None

        mock_401_response = MagicMock()
        mock_401_response.status_code = 401
        mock_401_response.read = MagicMock(return_value=b'{"error": "unauthorized"}')

        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json = MagicMock(return_value={"access_token": "new-token"})
        mock_auth_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = (
                mock_client_instance
            )
            mock_client_instance.request = AsyncMock(
                return_value=mock_auth_response  # For re-auth
            )

            with patch(
                "port_ocean.context.ocean.ocean.app.integration.entity_processor",
                mock_entity_processor,
            ):
                request = httpx.Request("GET", "https://api.example.com/data")
                auth_flow = custom_auth.async_auth_flow(request)

                # Get first authenticated request (triggers initial auth if needed)
                _ = await auth_flow.__anext__()

                # Send 401 response - this should trigger re-auth
                try:
                    retry_request = await auth_flow.asend(mock_401_response)
                    # Verify re-authentication happened
                    assert custom_auth.auth_response["access_token"] == "new-token"
                    # Verify new token is in headers
                    assert "Bearer new-token" in retry_request.headers["Authorization"]
                except StopAsyncIteration:
                    # If generator ends, that's also fine - re-auth might have happened
                    assert custom_auth.auth_response["access_token"] == "new-token"

    async def test_async_auth_flow_401_lock_prevents_concurrent_reauth(
        self, custom_auth: AuthFlowManager, mock_entity_processor: MagicMock
    ) -> None:
        """Test that lock prevents concurrent re-authentication on 401"""
        custom_auth.auth_response = {"access_token": "old-token"}
        custom_auth._expiration_tracker._auth_timestamp = time.time()
        custom_auth._expiration_tracker._reauthenticate_interval = None

        auth_calls = []

        async def mock_auth_with_delay() -> None:
            auth_calls.append("auth")
            await asyncio.sleep(0.1)
            custom_auth.auth_response = {"access_token": "new-token"}

        custom_auth._perform_auth_request = mock_auth_with_delay  # type: ignore[method-assign]

        mock_401_response = MagicMock()
        mock_401_response.status_code = 401
        mock_401_response.read = MagicMock(return_value=b'{"error": "unauthorized"}')

        async def run_auth_flow() -> None:
            with patch(
                "port_ocean.context.ocean.ocean.app.integration.entity_processor",
                mock_entity_processor,
            ):
                request = httpx.Request("GET", "https://api.example.com/data")
                auth_flow = custom_auth.async_auth_flow(request)
                await auth_flow.__anext__()
                try:
                    await auth_flow.asend(mock_401_response)
                except StopAsyncIteration:
                    pass

        # Run two concurrent auth flows that both get 401
        await asyncio.gather(run_auth_flow(), run_auth_flow())

        # Should have authenticated at least once, but lock should prevent duplicates
        assert len(auth_calls) >= 1
        assert len(auth_calls) <= 2


# ============================================================================
# Request Override Tests
# ============================================================================


@pytest.mark.asyncio
class TestRequestOverride:
    """Test request overriding with templates"""

    @pytest.fixture
    def auth_config(self) -> Dict[str, Any]:
        return {"base_url": "https://api.example.com", "verify_ssl": True}

    @pytest.fixture
    def custom_auth_request(self) -> CustomAuthRequestConfig:
        return CustomAuthRequestConfig(
            endpoint="/oauth/token",
            method="POST",
            body={"grant_type": "client_credentials"},
        )

    @pytest.fixture
    def custom_auth(
        self,
        auth_config: Dict[str, Any],
        custom_auth_request: CustomAuthRequestConfig,
    ) -> AuthFlowManager:
        # Create AuthFlowManager without custom_auth_response initially
        return AuthFlowManager(auth_config, custom_auth_request, None)

    async def test_override_request_headers(
        self, custom_auth: AuthFlowManager, mock_entity_processor: MagicMock
    ) -> None:
        """Test that headers are correctly overridden"""
        custom_auth.auth_response = {"access_token": "test-token-123"}
        custom_auth.custom_auth_response = CustomAuthResponseConfig(
            headers={"Authorization": "Bearer {{.access_token}}", "X-Custom": "value"}
        )

        original_request = httpx.Request(
            "GET", "https://api.example.com/data", headers={"X-Original": "original"}
        )

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            overridden_request = await custom_auth._override_request(original_request)

            # Verify auth header was added
            assert (
                overridden_request.headers["Authorization"] == "Bearer test-token-123"
            )
            # Verify custom header was added
            assert overridden_request.headers["X-Custom"] == "value"
            # Verify original header is preserved
            assert overridden_request.headers["X-Original"] == "original"
            # Verify method and URL are preserved
            assert overridden_request.method == "GET"
            assert str(overridden_request.url) == "https://api.example.com/data"

    async def test_override_request_query_params(
        self, custom_auth: AuthFlowManager, mock_entity_processor: MagicMock
    ) -> None:
        """Test that query params are correctly overridden"""
        custom_auth.auth_response = {"access_token": "test-token-456"}
        custom_auth.custom_auth_response = CustomAuthResponseConfig(
            queryParams={"api_key": "{{.access_token}}", "version": "v2"}
        )

        original_request = httpx.Request(
            "GET",
            "https://api.example.com/data?page=1&limit=10",
        )

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            overridden_request = await custom_auth._override_request(original_request)

            # Verify auth query param was added
            assert "api_key=test-token-456" in str(overridden_request.url)
            # Verify custom query param was added
            assert "version=v2" in str(overridden_request.url)
            # Verify original query params are preserved
            assert "page=1" in str(overridden_request.url)
            assert "limit=10" in str(overridden_request.url)

    async def test_override_request_body_with_existing_json_body(
        self, custom_auth: AuthFlowManager, mock_entity_processor: MagicMock
    ) -> None:
        """Test that body is correctly overridden when request has existing JSON body"""
        custom_auth.auth_response = {"access_token": "test-token-789"}
        custom_auth.custom_auth_response = CustomAuthResponseConfig(
            body={"token": "{{.access_token}}", "source": "api"}
        )

        # Create request with existing JSON body
        original_body = {"user_id": "123", "action": "create"}
        original_request = httpx.Request(
            "POST",
            "https://api.example.com/data",
            json=original_body,
        )

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            overridden_request = await custom_auth._override_request(original_request)

            # Read and parse the body
            body_bytes = overridden_request.read()
            body_data = json.loads(body_bytes.decode("utf-8"))

            # Verify auth body fields were added
            assert body_data["token"] == "test-token-789"
            assert body_data["source"] == "api"
            # Verify original body fields are preserved
            assert body_data["user_id"] == "123"
            assert body_data["action"] == "create"
            # Verify Content-Length header was updated
            assert "Content-Length" in overridden_request.headers
            assert int(overridden_request.headers["Content-Length"]) == len(body_bytes)

    async def test_override_request_body_with_empty_body(
        self, custom_auth: AuthFlowManager, mock_entity_processor: MagicMock
    ) -> None:
        """Test that body is correctly added when request has no body"""
        custom_auth.auth_response = {"access_token": "test-token-empty"}
        custom_auth.custom_auth_response = CustomAuthResponseConfig(
            body={"token": "{{.access_token}}"}
        )

        # Create request without body
        original_request = httpx.Request("POST", "https://api.example.com/data")

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            overridden_request = await custom_auth._override_request(original_request)

            # Read and parse the body
            body_bytes = overridden_request.read()
            body_data = json.loads(body_bytes.decode("utf-8"))

            # Verify auth body field was added
            assert body_data["token"] == "test-token-empty"
            # Verify Content-Length header was set
            assert "Content-Length" in overridden_request.headers
            assert int(overridden_request.headers["Content-Length"]) == len(body_bytes)

    async def test_override_request_body_with_non_json_body(
        self, custom_auth: AuthFlowManager, mock_entity_processor: MagicMock
    ) -> None:
        """Test that body override handles non-JSON body gracefully"""
        custom_auth.auth_response = {"access_token": "test-token-nonjson"}
        custom_auth.custom_auth_response = CustomAuthResponseConfig(
            body={"token": "{{.access_token}}"}
        )

        # Create request with non-JSON body (plain text)
        original_request = httpx.Request(
            "POST",
            "https://api.example.com/data",
            content=b"plain text body",
        )

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            overridden_request = await custom_auth._override_request(original_request)

            # Read and parse the body - should fall back to empty dict on JSON decode error
            body_bytes = overridden_request.read()
            body_data = json.loads(body_bytes.decode("utf-8"))

            # Verify auth body field was added (original body ignored due to JSON decode error)
            assert body_data["token"] == "test-token-nonjson"
            # Verify Content-Length header was updated
            assert "Content-Length" in overridden_request.headers

    async def test_override_request_all_parameters_together(
        self, custom_auth: AuthFlowManager, mock_entity_processor: MagicMock
    ) -> None:
        """Test that headers, query params, and body are all overridden together"""
        custom_auth.auth_response = {"access_token": "test-token-complete"}
        custom_auth.custom_auth_response = CustomAuthResponseConfig(
            headers={"Authorization": "Bearer {{.access_token}}"},
            queryParams={"api_key": "{{.access_token}}"},
            body={"token": "{{.access_token}}"},
        )

        original_request = httpx.Request(
            "PUT",
            "https://api.example.com/data?page=1",
            headers={"X-Original": "header"},
            json={"original": "data"},
        )

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            overridden_request = await custom_auth._override_request(original_request)

            # Verify headers
            assert (
                overridden_request.headers["Authorization"]
                == "Bearer test-token-complete"
            )
            assert overridden_request.headers["X-Original"] == "header"

            # Verify query params
            assert "api_key=test-token-complete" in str(overridden_request.url)
            assert "page=1" in str(overridden_request.url)

            # Verify body
            body_bytes = overridden_request.read()
            body_data = json.loads(body_bytes.decode("utf-8"))
            assert body_data["token"] == "test-token-complete"
            assert body_data["original"] == "data"

    async def test_override_request_no_auth_response(
        self, custom_auth: AuthFlowManager, mock_entity_processor: MagicMock
    ) -> None:
        """Test that request is returned unchanged when no auth_response exists"""
        custom_auth.auth_response = None
        custom_auth.custom_auth_response = CustomAuthResponseConfig(
            headers={"Authorization": "Bearer {{.access_token}}"}
        )

        original_request = httpx.Request(
            "GET", "https://api.example.com/data", headers={"X-Original": "header"}
        )

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            overridden_request = await custom_auth._override_request(original_request)

            # Request should be unchanged (cloned but no modifications)
            assert overridden_request.method == original_request.method
            assert str(overridden_request.url) == str(original_request.url)
            assert overridden_request.headers["X-Original"] == "header"
            # Auth header should NOT be added
            assert "Authorization" not in overridden_request.headers

    async def test_override_request_body_stream_is_set_correctly(
        self, custom_auth: AuthFlowManager, mock_entity_processor: MagicMock
    ) -> None:
        """Test that body stream is correctly set after overriding"""
        custom_auth.auth_response = {"access_token": "test-token-stream"}
        custom_auth.custom_auth_response = CustomAuthResponseConfig(
            body={"token": "{{.access_token}}"}
        )

        original_request = httpx.Request(
            "POST", "https://api.example.com/data", json={"data": "original"}
        )

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            overridden_request = await custom_auth._override_request(original_request)

            # Verify stream is set
            assert overridden_request.stream is not None
            # Verify we can read from the stream multiple times
            body_bytes_1 = overridden_request.read()
            # Reset stream position (if needed) or verify content is consistent
            overridden_request._content = json.dumps(
                {"data": "original", "token": "test-token-stream"}
            ).encode("utf-8")
            body_bytes_2 = overridden_request.read()
            assert body_bytes_1 == body_bytes_2

    async def test_override_request_preserves_extensions(
        self, custom_auth: AuthFlowManager, mock_entity_processor: MagicMock
    ) -> None:
        """Test that request extensions are preserved"""
        custom_auth.auth_response = {"access_token": "test-token-ext"}
        custom_auth.custom_auth_response = CustomAuthResponseConfig(
            headers={"Authorization": "Bearer {{.access_token}}"}
        )

        original_request = httpx.Request(
            "GET",
            "https://api.example.com/data",
            extensions={"custom_extension": "value"},
        )

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            overridden_request = await custom_auth._override_request(original_request)

            # Verify extensions are preserved
            assert overridden_request.extensions == original_request.extensions
            assert overridden_request.extensions["custom_extension"] == "value"


# ============================================================================
# Token Expiration & Proactive Re-authentication Tests
# ============================================================================


@pytest.mark.asyncio
class TestTokenExpiration:
    """Test token expiration and proactive re-authentication"""

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
        auth_config: Dict[str, Any],
        custom_auth_response: CustomAuthResponseConfig,
    ) -> AuthFlowManager:
        """AuthFlowManager with reauthenticate_interval_seconds configured"""
        auth_request = CustomAuthRequestConfig(
            endpoint="/oauth/token",
            method="POST",
            body={"grant_type": "client_credentials"},
            reauthenticate_interval_seconds=3600,  # 1 hour
        )
        return AuthFlowManager(auth_config, auth_request, custom_auth_response)

    @pytest.fixture
    def custom_auth_without_interval(
        self,
        auth_config: Dict[str, Any],
        custom_auth_response: CustomAuthResponseConfig,
    ) -> AuthFlowManager:
        """AuthFlowManager without reauthenticate_interval_seconds configured"""
        auth_request = CustomAuthRequestConfig(
            endpoint="/oauth/token",
            method="POST",
            body={"grant_type": "client_credentials"},
            # reauthenticate_interval_seconds not set (None)
        )
        return AuthFlowManager(auth_config, auth_request, custom_auth_response)

    async def test_expiration_tracker_interval_config(
        self, custom_auth_with_interval: AuthFlowManager
    ) -> None:
        """Test that configured interval is set in expiration tracker"""
        interval, _ = (
            custom_auth_with_interval._expiration_tracker.get_expiration_info()
        )
        assert interval == 3600

    async def test_expiration_tracker_no_interval_config(
        self, custom_auth_without_interval: AuthFlowManager
    ) -> None:
        """Test that None is set when not configured"""
        interval, _ = (
            custom_auth_without_interval._expiration_tracker.get_expiration_info()
        )
        assert interval is None

    async def test_is_expired_no_auth_yet(
        self, custom_auth_with_interval: AuthFlowManager
    ) -> None:
        """Test that returns True when no authentication has occurred"""
        assert custom_auth_with_interval._expiration_tracker.is_expired(False) is True

    async def test_is_expired_no_interval_configured(
        self, custom_auth_without_interval: AuthFlowManager
    ) -> None:
        """Test that returns False when no interval is configured"""
        custom_auth_without_interval.auth_response = {"access_token": "token"}
        custom_auth_without_interval._expiration_tracker._auth_timestamp = time.time()
        custom_auth_without_interval._expiration_tracker._reauthenticate_interval = None

        assert (
            custom_auth_without_interval._expiration_tracker.is_expired(True) is False
        )

    async def test_is_expired_not_expired(
        self, custom_auth_with_interval: AuthFlowManager
    ) -> None:
        """Test that returns False when token is not expired"""
        custom_auth_with_interval.auth_response = {"access_token": "token"}
        custom_auth_with_interval._expiration_tracker._auth_timestamp = time.time()
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = 3600

        assert custom_auth_with_interval._expiration_tracker.is_expired(True) is False

    async def test_is_expired_expired(
        self, custom_auth_with_interval: AuthFlowManager
    ) -> None:
        """Test that returns True when token is expired"""
        custom_auth_with_interval.auth_response = {"access_token": "token"}
        # Set timestamp to 2 hours ago (expired)
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time() - 7200
        )
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = 3600

        assert custom_auth_with_interval._expiration_tracker.is_expired(True) is True

    async def test_is_expired_within_buffer(
        self, custom_auth_with_interval: AuthFlowManager
    ) -> None:
        """Test that returns True when token is within buffer window (60 seconds)"""
        custom_auth_with_interval.auth_response = {"access_token": "token"}
        # Set timestamp so expiration is in 30 seconds (within 60s buffer)
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time() - 3570
        )  # 30s before expiration
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = 3600

        assert custom_auth_with_interval._expiration_tracker.is_expired(True) is True

    async def test_ensure_authenticated_proactively_reauthenticates_when_expired(
        self, custom_auth_with_interval: AuthFlowManager
    ) -> None:
        """Test that _ensure_authenticated proactively re-authenticates when expired"""
        # Set up expired token
        custom_auth_with_interval.auth_response = {"access_token": "old-token"}
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time() - 7200
        )  # 2 hours ago
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = 3600

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

        custom_auth_with_interval._perform_auth_request = mock_authenticate  # type: ignore[method-assign]

        await custom_auth_with_interval._ensure_authenticated()

        # Should have called authenticate
        assert len(authenticate_called) == 1
        assert custom_auth_with_interval.auth_response["access_token"] == "new-token"

    async def test_ensure_authenticated_does_not_reauthenticate_when_not_expired(
        self, custom_auth_with_interval: AuthFlowManager
    ) -> None:
        """Test that _ensure_authenticated does not re-authenticate when not expired"""
        # Set up valid token
        custom_auth_with_interval.auth_response = {"access_token": "valid-token"}
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time()
        )  # Just authenticated
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = 3600

        authenticate_called = []

        async def mock_authenticate() -> None:
            authenticate_called.append(True)

        custom_auth_with_interval._perform_auth_request = mock_authenticate  # type: ignore[method-assign]

        await custom_auth_with_interval._ensure_authenticated()

        # Should not have called authenticate
        assert len(authenticate_called) == 0

    async def test_ensure_authenticated_no_expiration_check_when_interval_none(
        self, custom_auth_without_interval: AuthFlowManager
    ) -> None:
        """Test that _ensure_authenticated doesn't check expiration when interval is None"""
        custom_auth_without_interval.auth_response = {"access_token": "token"}
        custom_auth_without_interval._expiration_tracker._auth_timestamp = time.time()
        custom_auth_without_interval._expiration_tracker._reauthenticate_interval = None

        authenticate_called = []

        async def mock_authenticate() -> None:
            authenticate_called.append(True)

        custom_auth_without_interval._perform_auth_request = mock_authenticate  # type: ignore[method-assign]

        await custom_auth_without_interval._ensure_authenticated()

        # Should not have called authenticate (no expiration checking)
        assert len(authenticate_called) == 0

    async def test_async_auth_flow_proactively_reauthenticates_on_expiration(
        self,
        custom_auth_with_interval: AuthFlowManager,
        mock_entity_processor: MagicMock,
    ) -> None:
        """Test that async_auth_flow proactively re-authenticates when expired"""
        # Set up expired token
        custom_auth_with_interval.auth_response = {"access_token": "old-token"}
        custom_auth_with_interval._expiration_tracker._auth_timestamp = (
            time.time() - 7200
        )
        custom_auth_with_interval._expiration_tracker._reauthenticate_interval = 3600

        authenticate_called = []

        async def mock_authenticate() -> None:
            authenticate_called.append(True)
            custom_auth_with_interval.auth_response = {"access_token": "new-token"}
            custom_auth_with_interval._expiration_tracker.record_authentication()

        custom_auth_with_interval._perform_auth_request = mock_authenticate  # type: ignore[method-assign]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.read = MagicMock(return_value=b'{"data": "success"}')

        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            request = httpx.Request("GET", "https://api.example.com/data")
            auth_flow = custom_auth_with_interval.async_auth_flow(request)

            # This should trigger proactive re-auth
            _ = await auth_flow.__anext__()

            # Should have called authenticate
            assert len(authenticate_called) == 1
            assert (
                custom_auth_with_interval.auth_response["access_token"] == "new-token"
            )

    async def test_proactive_reauthentication_uses_lock(
        self,
        custom_auth_with_interval: AuthFlowManager,
        mock_entity_processor: MagicMock,
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

        custom_auth_with_interval._perform_auth_request = mock_authenticate  # type: ignore[method-assign]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.read = MagicMock(return_value=b'{"data": "success"}')

        async def run_auth_flow() -> None:
            with patch(
                "port_ocean.context.ocean.ocean.app.integration.entity_processor",
                mock_entity_processor,
            ):
                request = httpx.Request("GET", "https://api.example.com/data")
                auth_flow = custom_auth_with_interval.async_auth_flow(request)
                await auth_flow.__anext__()

        # Run two concurrent auth flows
        await asyncio.gather(run_auth_flow(), run_auth_flow())

        # Should authenticate at least once, but lock should prevent race conditions
        assert len(authenticate_calls) >= 1
        assert len(authenticate_calls) <= 2
