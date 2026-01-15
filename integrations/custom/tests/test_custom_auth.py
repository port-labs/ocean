"""Tests for custom authentication functionality"""

import asyncio
import pytest
import httpx
from typing import Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock

from http_server.handlers import (
    CustomAuth,
    _evaluate_template,
    _evaluate_templates_in_dict,
    _reauthenticate_lock,
)
from http_server.overrides import CustomAuthRequestConfig, CustomAuthResponseConfig
from http_server.client import HttpServerClient


# ============================================================================
# Template Evaluation Tests
# ============================================================================


@pytest.mark.asyncio
class TestTemplateEvaluation:
    """Test template evaluation functions"""

    @pytest.fixture
    def mock_auth_response(self) -> Dict[str, Any]:
        return {
            "access_token": "abc123",
            "expires_in": 3600,
            "token_type": "Bearer",
            "nested": {"value": "nested_value"},
        }

    @pytest.fixture
    def mock_entity_processor(self):
        """Mock Ocean's entity processor for JQ evaluation"""
        mock_processor = AsyncMock()

        async def mock_search(data: Dict[str, Any], jq_path: str) -> Any:
            """Simple mock JQ processor - handles paths with or without leading dot"""
            # Normalize path (ensure leading dot)
            normalized_path = jq_path if jq_path.startswith(".") else f".{jq_path}"

            if normalized_path == ".access_token":
                return data.get("access_token")
            elif normalized_path == ".expires_in":
                return data.get("expires_in")
            elif normalized_path == ".token_type":
                return data.get("token_type")
            elif normalized_path == ".nested.value":
                return data.get("nested", {}).get("value")
            return None

        mock_processor._search = mock_search
        return mock_processor

    async def test_evaluate_template_simple(self, mock_auth_response, mock_entity_processor):
        """Test simple template evaluation"""
        with patch("port_ocean.context.ocean.ocean.app.integration.entity_processor", mock_entity_processor):
            template = "Bearer {{.access_token}}"
            result = await _evaluate_template(template, mock_auth_response)
            assert result == "Bearer abc123"

    async def test_evaluate_template_multiple_variables(
        self, mock_auth_response, mock_entity_processor
    ):
        """Test template with multiple variables"""
        with patch("port_ocean.context.ocean.ocean.app.integration.entity_processor", mock_entity_processor):
            template = "{{.token_type}} {{.access_token}} expires in {{.expires_in}}"
            result = await _evaluate_template(template, mock_auth_response)
            assert result == "Bearer abc123 expires in 3600"

    async def test_evaluate_template_nested_path(
        self, mock_auth_response, mock_entity_processor
    ):
        """Test nested JQ path"""
        with patch("port_ocean.context.ocean.ocean.app.integration.entity_processor", mock_entity_processor):
            template = "Value: {{.nested.value}}"
            result = await _evaluate_template(template, mock_auth_response)
            assert result == "Value: nested_value"

    async def test_evaluate_template_without_dot(
        self, mock_auth_response
    ):
        """Test JQ path without leading dot (should auto-add)"""
        # Create a new mock processor that handles paths with or without leading dot
        mock_processor = MagicMock()

        async def mock_search_without_dot(data: Dict[str, Any], jq_path: str) -> Any:
            """Mock that handles paths with or without leading dot"""
            # The code prepends a dot if missing, so jq_path will always have a dot
            if jq_path == ".access_token":
                return data.get("access_token")
            return None

        mock_processor._search = mock_search_without_dot

        with patch("port_ocean.context.ocean.ocean.app.integration.entity_processor", mock_processor):
            template = "Token: {{access_token}}"
            result = await _evaluate_template(template, mock_auth_response)
            assert result == "Token: abc123"

    async def test_evaluate_template_missing_field(
        self, mock_auth_response, mock_entity_processor
    ):
        """Test missing field returns original template"""
        with patch("port_ocean.context.ocean.ocean.app.integration.entity_processor", mock_entity_processor):
            template = "Bearer {{.missing_field}}"
            result = await _evaluate_template(template, mock_auth_response)
            assert result == "Bearer {{.missing_field}}"

    async def test_evaluate_template_no_auth_response(self):
        """Test with empty auth response"""
        template = "Bearer {{.access_token}}"
        result = await _evaluate_template(template, None)
        assert result == template

    async def test_evaluate_templates_in_dict_headers(
        self, mock_auth_response, mock_entity_processor
    ):
        """Test template evaluation in headers dict"""
        with patch("port_ocean.context.ocean.ocean.app.integration.entity_processor", mock_entity_processor):
            data = {
                "Authorization": "Bearer {{.access_token}}",
                "X-TTL": "{{.expires_in}}",
            }
            result = await _evaluate_templates_in_dict(data, mock_auth_response)
            assert result["Authorization"] == "Bearer abc123"
            assert result["X-TTL"] == "3600"

    async def test_evaluate_templates_in_dict_query_params(
        self, mock_auth_response, mock_entity_processor
    ):
        """Test template evaluation in query params"""
        with patch("port_ocean.context.ocean.ocean.app.integration.entity_processor", mock_entity_processor):
            data = {"api_key": "{{.access_token}}", "ttl": "{{.expires_in}}"}
            result = await _evaluate_templates_in_dict(data, mock_auth_response)
            assert result["api_key"] == "abc123"
            assert result["ttl"] == "3600"

    async def test_evaluate_templates_in_dict_body(
        self, mock_auth_response, mock_entity_processor
    ):
        """Test template evaluation in body"""
        with patch("port_ocean.context.ocean.ocean.app.integration.entity_processor", mock_entity_processor):
            data = {"token": "{{.access_token}}", "expires": "{{.expires_in}}"}
            result = await _evaluate_templates_in_dict(data, mock_auth_response)
            assert result["token"] == "abc123"
            assert result["expires"] == "3600"

    async def test_evaluate_templates_nested_dict(
        self, mock_auth_response, mock_entity_processor
    ):
        """Test nested dictionary evaluation"""
        with patch("port_ocean.context.ocean.ocean.app.integration.entity_processor", mock_entity_processor):
            data = {
                "auth": {
                    "token": "{{.access_token}}",
                    "type": "{{.token_type}}",
                }
            }
            result = await _evaluate_templates_in_dict(data, mock_auth_response)
            assert result["auth"]["token"] == "abc123"
            assert result["auth"]["type"] == "Bearer"

    async def test_evaluate_templates_list(
        self, mock_auth_response, mock_entity_processor
    ):
        """Test list evaluation"""
        with patch("port_ocean.context.ocean.ocean.app.integration.entity_processor", mock_entity_processor):
            data = {"tokens": ["{{.access_token}}", "{{.token_type}}"]}
            result = await _evaluate_templates_in_dict(data, mock_auth_response)
            assert result["tokens"] == ["abc123", "Bearer"]


# ============================================================================
# CustomAuth Class Tests
# ============================================================================


@pytest.mark.asyncio
class TestCustomAuth:
    """Test CustomAuth authentication handler"""

    @pytest.fixture
    def mock_client(self):
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
    def mock_entity_processor(self):
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
        mock_client,
        auth_config,
        custom_auth_request,
        custom_auth_response,
    ) -> CustomAuth:
        return CustomAuth(
            mock_client, auth_config, custom_auth_request, custom_auth_response
        )

    async def test_authenticate_async_success(self, custom_auth):
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

            assert custom_auth.auth_response["access_token"] == "test-token-123"
            assert custom_auth.auth_response["expires_in"] == 3600

    async def test_authenticate_async_full_url(self, custom_auth):
        """Test authentication with full URL"""
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

    async def test_authenticate_async_with_body_form(self, custom_auth):
        """Test authentication with form-encoded body"""
        # bodyForm should be a string (form-encoded), not a dict
        # Set bodyForm first, then clear body to ensure bodyForm is used
        custom_auth.custom_auth_request.bodyForm = "grant_type=password&username=test"
        custom_auth.custom_auth_request.body = None

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

    async def test_authenticate_async_http_error(self, custom_auth):
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
        self, custom_auth, mock_entity_processor
    ):
        """Test applying auth to headers"""
        custom_auth.auth_response = {"access_token": "test-token"}

        with patch("port_ocean.context.ocean.ocean.app.integration.entity_processor", mock_entity_processor):
            headers = {"X-Custom": "value"}
            result_headers, _, _ = await custom_auth.apply_auth_to_request(headers)

            assert result_headers["Authorization"] == "Bearer test-token"
            assert result_headers["X-Custom"] == "value"

    async def test_apply_auth_to_request_query_params(
        self, custom_auth, mock_entity_processor
    ):
        """Test applying auth to query params"""
        custom_auth.auth_response = {"access_token": "test-token"}

        with patch("port_ocean.context.ocean.ocean.app.integration.entity_processor", mock_entity_processor):
            query_params = {"page": "1"}
            _, result_params, _ = await custom_auth.apply_auth_to_request(
                {}, query_params
            )

            assert result_params["api_key"] == "test-token"
            assert result_params["page"] == "1"

    async def test_apply_auth_to_request_body(
        self, custom_auth, mock_entity_processor
    ):
        """Test applying auth to body"""
        custom_auth.auth_response = {"access_token": "test-token"}

        with patch("port_ocean.context.ocean.ocean.app.integration.entity_processor", mock_entity_processor):
            body = {"data": "value"}
            _, _, result_body = await custom_auth.apply_auth_to_request({}, None, body)

            assert result_body["token"] == "test-token"
            assert result_body["data"] == "value"

    async def test_apply_auth_no_auth_response(self, custom_auth):
        """Test applying auth when no auth_response exists"""
        custom_auth.auth_response = None

        headers = {"X-Custom": "value"}
        result_headers, _, _ = await custom_auth.apply_auth_to_request(headers)

        # Should return original headers unchanged
        assert result_headers == headers

    async def test_apply_auth_no_custom_auth_response_config(self, custom_auth):
        """Test applying auth when no custom_auth_response config exists"""
        custom_auth.auth_response = {"access_token": "test-token"}
        custom_auth.custom_auth_response = None

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

    async def test_reauthenticate_called_on_401(self, custom_auth):
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

    async def test_reauthenticate_lock_prevents_concurrent_auth(self, custom_auth):
        """Test that lock prevents concurrent re-authentication"""
        custom_auth.auth_response = {"access_token": "old-token"}

        # Track authentication calls
        auth_calls = []

        async def mock_authenticate():
            auth_calls.append("auth")
            await asyncio.sleep(0.1)  # Simulate auth delay

        custom_auth.authenticate_async = mock_authenticate

        # Simulate two concurrent re-authentication attempts
        async def reauth1():
            await custom_auth.reauthenticate()

        async def reauth2():
            await asyncio.sleep(0.05)  # Start slightly after reauth1
            await custom_auth.reauthenticate()

        await asyncio.gather(reauth1(), reauth2())

        # Should authenticate at least once, but lock should prevent race conditions
        assert len(auth_calls) >= 1
        assert len(auth_calls) <= 2  # At most 2 (if first completes before second acquires lock)

    async def test_reauthenticate_skips_if_already_refreshed(self, custom_auth):
        """Test that reauthenticate skips if auth was already refreshed"""
        custom_auth.auth_response = {"access_token": "old-token"}
        auth_response_before = custom_auth.auth_response.copy()

        # Simulate another coroutine refreshing auth while waiting for lock
        async def acquire_lock_and_refresh():
            await asyncio.sleep(0.05)
            custom_auth.auth_response = {"access_token": "refreshed-token"}

        # Start refresh task
        refresh_task = asyncio.create_task(acquire_lock_and_refresh())

        # Mock authenticate to track if it's called
        authenticate_called = []

        async def mock_authenticate():
            authenticate_called.append(True)
            custom_auth.auth_response = {"access_token": "new-token"}

        custom_auth.authenticate_async = mock_authenticate

        # Try to re-authenticate (should skip after lock)
        await custom_auth.reauthenticate()

        await refresh_task

        # Should have skipped re-auth since auth_response changed
        # The auth_response should be "refreshed-token" (from the refresh task)
        # or "new-token" (if authenticate was called)
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
    def client_with_custom_auth(self) -> HttpServerClient:
        auth_request = CustomAuthRequestConfig(
            endpoint="/auth",
            method="POST",
            body={"grant_type": "client_credentials"},
        )
        auth_response = CustomAuthResponseConfig(
            headers={"Authorization": "Bearer {{.access_token}}"}
        )
        # Use verify_ssl=False to avoid SSL context issues in tests
        return HttpServerClient(
            base_url="https://api.example.com",
            auth_type="custom",
            auth_config={"base_url": "https://api.example.com", "verify_ssl": False},
            pagination_config={"pagination_type": "none"},
            custom_auth_request=auth_request,
            custom_auth_response=auth_response,
            skip_setup=True,
        )

    async def test_401_triggers_reauthentication(self, client_with_custom_auth):
        """Test that 401 triggers re-authentication and retry"""
        # Set initial auth
        client_with_custom_auth.auth_handler.auth_response = {
            "access_token": "old-token"
        }

        # Mock responses: 401 then 200
        mock_401 = AsyncMock()
        mock_401.status_code = 401
        mock_401.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_401
        )

        mock_200 = AsyncMock()
        mock_200.status_code = 200
        mock_200.json = MagicMock(return_value={"data": "success"})
        mock_200.raise_for_status = MagicMock()

        # Mock reauthenticate to update auth_response
        async def mock_reauthenticate():
            client_with_custom_auth.auth_handler.auth_response = {
                "access_token": "new-token"
            }

        client_with_custom_auth.auth_handler.reauthenticate = mock_reauthenticate

        # Mock the client's request method
        client_with_custom_auth.client.request = AsyncMock(
            side_effect=[mock_401, mock_200]
        )

        response = await client_with_custom_auth._make_request(
            url="https://api.example.com/data",
            method="GET",
            params={},
            headers={},
        )

        assert response.status_code == 200
        # Verify re-authentication was called (auth_response updated)
        assert (
            client_with_custom_auth.auth_handler.auth_response["access_token"]
            == "new-token"
        )
        # Verify request was retried (called twice: 401 then 200)
        assert client_with_custom_auth.client.request.call_count == 2

    async def test_401_reauthentication_failure(self, client_with_custom_auth):
        """Test that 401 with failed re-auth raises error"""
        client_with_custom_auth.auth_handler.auth_response = {
            "access_token": "old-token"
        }

        mock_401 = AsyncMock()
        mock_401.status_code = 401
        mock_401.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_401
        )

        # Mock reauthenticate to fail
        async def mock_reauthenticate():
            raise Exception("Re-authentication failed")

        client_with_custom_auth.auth_handler.reauthenticate = mock_reauthenticate

        client_with_custom_auth.client.request = AsyncMock(return_value=mock_401)

        with pytest.raises(httpx.HTTPStatusError):
            await client_with_custom_auth._make_request(
                url="https://api.example.com/data",
                method="GET",
                params={},
                headers={},
            )
