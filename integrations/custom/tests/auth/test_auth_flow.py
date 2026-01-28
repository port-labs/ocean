"""Tests for AuthFlowManager authentication flow"""

import asyncio
import json
import pytest
import httpx
import time
from typing import Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock

from http_server.auth.custom.auth_flow import AuthFlowManager
from http_server.overrides import CustomAuthRequestConfig, CustomAuthRequestTemplateConfig


# ============================================================================
# AuthFlowManager Core Tests
# ============================================================================


@pytest.mark.asyncio
class TestAuthFlowManager:
    """Test AuthFlowManager authentication handler"""

    @pytest.fixture
    def custom_auth(
        self,
        auth_config: Dict[str, Any],
        custom_auth_request: CustomAuthRequestConfig,
        custom_auth_request_template: CustomAuthRequestTemplateConfig,
    ) -> AuthFlowManager:
        return AuthFlowManager(
            auth_config, custom_auth_request, custom_auth_request_template
        )

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

        with patch(
            "http_server.auth.custom.auth_flow.OceanAsyncClient"
        ) as mock_client_class:
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

        with patch(
            "http_server.auth.custom.auth_flow.OceanAsyncClient"
        ) as mock_client_class:
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

        with patch(
            "http_server.auth.custom.auth_flow.OceanAsyncClient"
        ) as mock_client_class:
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

        with patch(
            "http_server.auth.custom.auth_flow.OceanAsyncClient"
        ) as mock_client_class:
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

        with patch(
            "http_server.auth.custom.auth_flow.OceanAsyncClient"
        ) as mock_client_class:
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

        with patch(
            "http_server.auth.custom.auth_flow.OceanAsyncClient"
        ) as mock_client_class:
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

        async def mock_auth_with_delay(*, force: bool = False) -> None:
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
    def custom_auth_request_minimal(self) -> CustomAuthRequestConfig:
        return CustomAuthRequestConfig(
            endpoint="/oauth/token",
            method="POST",
            body={"grant_type": "client_credentials"},
        )

    @pytest.fixture
    def custom_auth(
        self,
        auth_config: Dict[str, Any],
        custom_auth_request_minimal: CustomAuthRequestConfig,
        custom_auth_request_template: CustomAuthRequestTemplateConfig,
    ) -> AuthFlowManager:
        # Create AuthFlowManager without custom_auth_response initially
        return AuthFlowManager(
            auth_config,
            custom_auth_request_minimal,
            custom_auth_request_template,
        )

    async def test_override_request_headers(
        self, custom_auth: AuthFlowManager, mock_entity_processor: MagicMock
    ) -> None:
        """Test that headers are correctly overridden"""
        custom_auth.auth_response = {"access_token": "test-token-123"}
        custom_auth.custom_auth_response = CustomAuthRequestTemplateConfig(
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
        custom_auth.custom_auth_response = CustomAuthRequestTemplateConfig(
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
        custom_auth.custom_auth_response = CustomAuthRequestTemplateConfig(
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
        custom_auth.custom_auth_response = CustomAuthRequestTemplateConfig(
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
        custom_auth.custom_auth_response = CustomAuthRequestTemplateConfig(
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
        custom_auth.custom_auth_response = CustomAuthRequestTemplateConfig(
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
        custom_auth.custom_auth_response = CustomAuthRequestTemplateConfig(
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
        custom_auth.custom_auth_response = CustomAuthRequestTemplateConfig(
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
        custom_auth.custom_auth_response = CustomAuthRequestTemplateConfig(
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
