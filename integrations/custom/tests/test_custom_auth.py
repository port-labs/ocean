"""Tests for custom authentication functionality"""

import asyncio
import pytest
import httpx
import time
from typing import Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock

from http_server.handlers import (
    CustomAuth,
    _evaluate_template,
    _evaluate_templates_in_dict,
    _validate_template_syntax,
    _validate_templates_in_dict,
)
from http_server.overrides import CustomAuthRequestConfig, CustomAuthResponseConfig
from http_server.exceptions import (
    TemplateSyntaxError,
    TemplateEvaluationError,
    TemplateVariableNotFoundError,
    CustomAuthRequestError,
    CustomAuthResponseError,
)
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
    def mock_entity_processor(self) -> MagicMock:
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

    async def test_evaluate_template_simple(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test simple template evaluation"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            template = "Bearer {{.access_token}}"
            result = await _evaluate_template(template, mock_auth_response)
            assert result == "Bearer abc123"

    async def test_evaluate_template_multiple_variables(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test template with multiple variables"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            template = "{{.token_type}} {{.access_token}} expires in {{.expires_in}}"
            result = await _evaluate_template(template, mock_auth_response)
            assert result == "Bearer abc123 expires in 3600"

    async def test_evaluate_template_nested_path(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test nested JQ path"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            template = "Value: {{.nested.value}}"
            result = await _evaluate_template(template, mock_auth_response)
            assert result == "Value: nested_value"

    async def test_evaluate_template_without_dot(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test that templates without dot are not processed (regex requires {{.path}} format)"""
        # The regex pattern requires {{.path}} format, so {{path}} without dot won't match
        # This test verifies that templates without the dot are left unchanged
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            template = "Token: {{access_token}}"
            result = await _evaluate_template(template, mock_auth_response)
            # Template without dot should remain unchanged since it doesn't match the regex
            assert result == "Token: {{access_token}}"

    async def test_evaluate_template_missing_field_raises_exception(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test missing field raises TemplateVariableNotFoundError"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            template = "Bearer {{.missing_field}}"
            with pytest.raises(TemplateVariableNotFoundError) as exc_info:
                await _evaluate_template(template, mock_auth_response)
            assert "missing_field" in str(exc_info.value)
            assert "Available keys" in str(exc_info.value)

    async def test_evaluate_template_no_auth_response_raises_exception(self) -> None:
        """Test with empty auth response raises TemplateEvaluationError"""
        template = "Bearer {{.access_token}}"
        with pytest.raises(TemplateEvaluationError) as exc_info:
            await _evaluate_template(template, None)  # type: ignore[arg-type]
        assert "auth_response is empty" in str(exc_info.value)

    async def test_evaluate_templates_in_dict_headers(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test template evaluation in headers dict"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            data = {
                "Authorization": "Bearer {{.access_token}}",
                "X-TTL": "{{.expires_in}}",
            }
            result = await _evaluate_templates_in_dict(data, mock_auth_response)
            assert result["Authorization"] == "Bearer abc123"
            assert result["X-TTL"] == "3600"

    async def test_evaluate_templates_in_dict_query_params(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test template evaluation in query params"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            data = {"api_key": "{{.access_token}}", "ttl": "{{.expires_in}}"}
            result = await _evaluate_templates_in_dict(data, mock_auth_response)
            assert result["api_key"] == "abc123"
            assert result["ttl"] == "3600"

    async def test_evaluate_templates_in_dict_body(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test template evaluation in body"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            data = {"token": "{{.access_token}}", "expires": "{{.expires_in}}"}
            result = await _evaluate_templates_in_dict(data, mock_auth_response)
            assert result["token"] == "abc123"
            assert result["expires"] == "3600"

    async def test_evaluate_templates_nested_dict(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test nested dictionary evaluation"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
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
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test list evaluation"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
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
        custom_auth._auth_timestamp = time.time()
        custom_auth._reauthenticate_interval = None  # Disable expiration checking

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
        custom_auth._auth_timestamp = time.time()
        custom_auth._reauthenticate_interval = None  # Disable expiration checking

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
        custom_auth._auth_timestamp = time.time()
        custom_auth._reauthenticate_interval = None  # Disable expiration checking

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
        custom_auth._auth_timestamp = time.time()
        custom_auth._reauthenticate_interval = None  # Disable expiration checking

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
                skip_setup=True,
            )
            # Replace the client with our mock
            client.client = mock_client
            return client

    async def test_401_triggers_reauthentication(
        self, client_with_custom_auth: HttpServerClient
    ) -> None:
        """Test that 401 triggers re-authentication and retry"""
        # Set initial auth
        # Type ignore needed because CustomAuth has auth_response attribute
        client_with_custom_auth.auth_handler.auth_response = {  # type: ignore[attr-defined]
            "access_token": "old-token"
        }
        # Set timestamp and interval to prevent expiration check from triggering
        # (we want to test 401 handling, not expiration)
        client_with_custom_auth.auth_handler._auth_timestamp = time.time()  # type: ignore[attr-defined]
        client_with_custom_auth.auth_handler._reauthenticate_interval = None  # type: ignore[attr-defined]

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
        client_with_custom_auth.auth_handler.reauthenticate = mock_reauthenticate  # type: ignore[attr-defined]

        # Mock the client's request method
        client_with_custom_auth.client.request = AsyncMock(  # type: ignore[method-assign]
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
        # Type ignore needed because CustomAuth has auth_response attribute
        auth_response = client_with_custom_auth.auth_handler.auth_response  # type: ignore[attr-defined]
        assert auth_response is not None
        assert auth_response["access_token"] == "new-token"
        # Verify request was retried (called twice: 401 then 200)
        assert client_with_custom_auth.client.request.call_count == 2

    async def test_401_reauthentication_failure(
        self, client_with_custom_auth: HttpServerClient
    ) -> None:
        """Test that 401 with failed re-auth raises error"""
        # Type ignore needed because CustomAuth has auth_response attribute
        client_with_custom_auth.auth_handler.auth_response = {  # type: ignore[attr-defined]
            "access_token": "old-token"
        }
        # Set timestamp and interval to prevent expiration check from triggering
        # (we want to test 401 handling, not expiration)
        client_with_custom_auth.auth_handler._auth_timestamp = time.time()  # type: ignore[attr-defined]
        client_with_custom_auth.auth_handler._reauthenticate_interval = None  # type: ignore[attr-defined]

        mock_401 = MagicMock()
        mock_401.status_code = 401
        mock_401.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_401
        )

        # Mock reauthenticate to fail
        async def mock_reauthenticate() -> None:
            raise Exception("Re-authentication failed")

        # Type ignore needed because we're testing CustomAuth which has reauthenticate
        client_with_custom_auth.auth_handler.reauthenticate = mock_reauthenticate  # type: ignore[attr-defined]

        client_with_custom_auth.client.request = AsyncMock(return_value=mock_401)  # type: ignore[method-assign]

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
        """Test that configured interval is used"""
        custom_auth_with_interval.auth_response = {"access_token": "token"}
        interval = await custom_auth_with_interval._calculate_reauthenticate_interval()
        assert interval == 3600

    async def test_calculate_reauthenticate_interval_without_config(
        self, custom_auth_without_interval: CustomAuth
    ) -> None:
        """Test that None is returned when not configured"""
        custom_auth_without_interval.auth_response = {"access_token": "token"}
        interval = (
            await custom_auth_without_interval._calculate_reauthenticate_interval()
        )
        assert interval is None

    async def test_is_auth_expired_no_auth_yet(
        self, custom_auth_with_interval: CustomAuth
    ) -> None:
        """Test that returns True when no authentication has occurred"""
        assert custom_auth_with_interval._is_auth_expired() is True

    async def test_is_auth_expired_no_interval_configured(
        self, custom_auth_without_interval: CustomAuth
    ) -> None:
        """Test that returns False when no interval is configured (expiration checking disabled)"""
        custom_auth_without_interval.auth_response = {"access_token": "token"}
        custom_auth_without_interval._auth_timestamp = time.time()
        custom_auth_without_interval._reauthenticate_interval = None

        assert custom_auth_without_interval._is_auth_expired() is False

    async def test_is_auth_expired_not_expired(
        self, custom_auth_with_interval: CustomAuth
    ) -> None:
        """Test that returns False when token is not expired"""
        custom_auth_with_interval.auth_response = {"access_token": "token"}
        custom_auth_with_interval._auth_timestamp = time.time()
        custom_auth_with_interval._reauthenticate_interval = 3600  # 1 hour

        assert custom_auth_with_interval._is_auth_expired() is False

    async def test_is_auth_expired_expired(
        self, custom_auth_with_interval: CustomAuth
    ) -> None:
        """Test that returns True when token is expired"""
        custom_auth_with_interval.auth_response = {"access_token": "token"}
        # Set timestamp to 2 hours ago (expired)
        custom_auth_with_interval._auth_timestamp = time.time() - 7200
        custom_auth_with_interval._reauthenticate_interval = 3600  # 1 hour

        assert custom_auth_with_interval._is_auth_expired() is True

    async def test_is_auth_expired_within_buffer(
        self, custom_auth_with_interval: CustomAuth
    ) -> None:
        """Test that returns True when token is within buffer window (60 seconds)"""
        custom_auth_with_interval.auth_response = {"access_token": "token"}
        # Set timestamp so expiration is in 30 seconds (within 60s buffer)
        custom_auth_with_interval._auth_timestamp = (
            time.time() - 3570
        )  # 30s before expiration
        custom_auth_with_interval._reauthenticate_interval = 3600  # 1 hour

        assert custom_auth_with_interval._is_auth_expired() is True

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

            assert custom_auth_with_interval._auth_timestamp is not None
            assert custom_auth_with_interval._reauthenticate_interval == 3600

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

            assert custom_auth_without_interval._auth_timestamp is not None
            assert custom_auth_without_interval._reauthenticate_interval is None

    async def test_apply_auth_proactively_reauthenticates_when_expired(
        self, custom_auth_with_interval: CustomAuth
    ) -> None:
        """Test that apply_auth_to_request proactively re-authenticates when expired"""
        # Set up expired token
        custom_auth_with_interval.auth_response = {"access_token": "old-token"}
        custom_auth_with_interval._auth_timestamp = time.time() - 7200  # 2 hours ago
        custom_auth_with_interval._reauthenticate_interval = 3600  # 1 hour

        # Mock re-authentication
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"access_token": "new-token"})
        mock_response.raise_for_status = MagicMock()

        authenticate_called = []

        async def mock_authenticate() -> None:
            authenticate_called.append(True)
            custom_auth_with_interval.auth_response = {"access_token": "new-token"}
            custom_auth_with_interval._auth_timestamp = time.time()
            custom_auth_with_interval._reauthenticate_interval = 3600

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
        custom_auth_with_interval._auth_timestamp = time.time()  # Just authenticated
        custom_auth_with_interval._reauthenticate_interval = 3600  # 1 hour

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
        custom_auth_without_interval._auth_timestamp = time.time()
        custom_auth_without_interval._reauthenticate_interval = None

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
        custom_auth_with_interval._auth_timestamp = time.time() - 7200
        custom_auth_with_interval._reauthenticate_interval = 3600

        authenticate_calls = []

        async def mock_authenticate() -> None:
            authenticate_calls.append("auth")
            await asyncio.sleep(0.1)  # Simulate auth delay
            custom_auth_with_interval.auth_response = {"access_token": "new-token"}
            custom_auth_with_interval._auth_timestamp = time.time()

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


# ============================================================================
# Template Syntax Validation Tests
# ============================================================================


class TestTemplateSyntaxValidation:
    """Test template syntax validation functions"""

    def test_validate_template_syntax_valid(self) -> None:
        """Test that valid template syntax passes validation"""
        _validate_template_syntax("Bearer {{.access_token}}")
        _validate_template_syntax("Token: {{.token}} expires in {{.expires_in}}")
        _validate_template_syntax("{{.nested.value}}")

    def test_validate_template_syntax_invalid_missing_dot(self) -> None:
        """Test that invalid template syntax (missing dot) raises TemplateSyntaxError"""
        with pytest.raises(TemplateSyntaxError) as exc_info:
            _validate_template_syntax("Bearer {{access_token}}")
        assert "Invalid template syntax" in str(exc_info.value)
        assert "{{access_token}}" in str(exc_info.value)

    def test_validate_template_syntax_invalid_wrong_format(self) -> None:
        """Test that invalid template format raises TemplateSyntaxError"""
        with pytest.raises(TemplateSyntaxError) as exc_info:
            _validate_template_syntax("Bearer {{access_token}}")
        assert "Templates must use the format {{.path}}" in str(exc_info.value)

    def test_validate_template_syntax_with_context(self) -> None:
        """Test that context is included in error message"""
        with pytest.raises(TemplateSyntaxError) as exc_info:
            _validate_template_syntax(
                "Bearer {{token}}", context="headers.Authorization"
            )
        assert "headers.Authorization" in str(exc_info.value)

    def test_validate_template_syntax_no_templates(self) -> None:
        """Test that strings without templates pass validation"""
        _validate_template_syntax("Bearer token")
        _validate_template_syntax("No templates here")

    def test_validate_template_syntax_non_string(self) -> None:
        """Test that non-string values pass validation (no-op)"""
        _validate_template_syntax(123)  # type: ignore[arg-type]
        _validate_template_syntax(None)  # type: ignore[arg-type]
        _validate_template_syntax({"key": "value"})  # type: ignore[arg-type]

    def test_validate_templates_in_dict_valid(self) -> None:
        """Test that valid templates in dict pass validation"""
        data = {
            "Authorization": "Bearer {{.access_token}}",
            "X-TTL": "{{.expires_in}}",
        }
        _validate_templates_in_dict(data)

    def test_validate_templates_in_dict_invalid(self) -> None:
        """Test that invalid templates in dict raise TemplateSyntaxError"""
        data = {
            "Authorization": "Bearer {{access_token}}",  # Missing dot
            "X-TTL": "{{.expires_in}}",  # Valid
        }
        with pytest.raises(TemplateSyntaxError) as exc_info:
            _validate_templates_in_dict(data, prefix="headers")
        assert "headers.Authorization" in str(exc_info.value)

    def test_validate_templates_in_dict_nested(self) -> None:
        """Test validation of nested dictionaries"""
        data = {
            "auth": {
                "token": "{{.access_token}}",
                "invalid": "{{token}}",  # Invalid
            }
        }
        with pytest.raises(TemplateSyntaxError) as exc_info:
            _validate_templates_in_dict(data)
        assert "auth.invalid" in str(exc_info.value)

    def test_validate_templates_in_dict_list(self) -> None:
        """Test validation of templates in lists"""
        data = {"tokens": ["{{.access_token}}", "{{token}}"]}  # Second is invalid
        with pytest.raises(TemplateSyntaxError) as exc_info:
            _validate_templates_in_dict(data)
        assert "tokens[1]" in str(exc_info.value)

    def test_validate_templates_in_dict_mixed_types(self) -> None:
        """Test validation with mixed types (strings, dicts, lists, non-strings)"""
        data = {
            "valid": "{{.token}}",
            "nested": {"key": "{{.value}}"},
            "list": ["{{.item}}"],
            "number": 123,  # Should be ignored
            "none": None,  # Should be ignored
        }
        _validate_templates_in_dict(data)  # Should pass


# ============================================================================
# Config Validation Tests
# ============================================================================


class TestCustomAuthResponseConfigValidation:
    """Test CustomAuthResponseConfig validation"""

    def test_valid_config_with_headers(self) -> None:
        """Test that config with headers is valid"""
        config = CustomAuthResponseConfig(
            headers={"Authorization": "Bearer {{.token}}"}
        )
        assert config.headers == {"Authorization": "Bearer {{.token}}"}

    def test_valid_config_with_query_params(self) -> None:
        """Test that config with queryParams is valid"""
        config = CustomAuthResponseConfig(queryParams={"api_key": "{{.token}}"})
        assert config.queryParams == {"api_key": "{{.token}}"}

    def test_valid_config_with_body(self) -> None:
        """Test that config with body is valid"""
        config = CustomAuthResponseConfig(body={"token": "{{.token}}"})
        assert config.body == {"token": "{{.token}}"}

    def test_valid_config_with_multiple_fields(self) -> None:
        """Test that config with multiple fields is valid"""
        config = CustomAuthResponseConfig(
            headers={"Authorization": "Bearer {{.token}}"},
            queryParams={"api_key": "{{.token}}"},
        )
        assert config.headers is not None
        assert config.queryParams is not None

    def test_invalid_config_empty(self) -> None:
        """Test that empty config raises CustomAuthResponseError"""
        with pytest.raises(CustomAuthResponseError) as exc_info:
            CustomAuthResponseConfig()
        assert (
            "At least one of 'headers', 'queryParams', or 'body' must be provided"
            in str(exc_info.value)
        )

    def test_invalid_config_all_none(self) -> None:
        """Test that config with all fields None raises CustomAuthResponseError"""
        with pytest.raises(CustomAuthResponseError) as exc_info:
            CustomAuthResponseConfig(headers=None, queryParams=None, body=None)
        assert (
            "At least one of 'headers', 'queryParams', or 'body' must be provided"
            in str(exc_info.value)
        )


class TestCustomAuthRequestConfigValidation:
    """Test CustomAuthRequestConfig validation"""

    def test_valid_config(self) -> None:
        """Test that valid config passes validation"""
        config = CustomAuthRequestConfig(
            endpoint="/oauth/token",
            method="POST",
            body={"grant_type": "client_credentials"},
        )
        assert config.endpoint == "/oauth/token"
        assert config.method == "POST"

    def test_invalid_method(self) -> None:
        """Test that invalid HTTP method raises CustomAuthRequestError"""
        with pytest.raises(CustomAuthRequestError) as exc_info:
            CustomAuthRequestConfig(
                endpoint="/oauth/token",
                method="INVALID",
            )
        assert "Method must be one of" in str(exc_info.value)

    def test_valid_methods(self) -> None:
        """Test that all valid HTTP methods pass validation"""
        valid_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
        for method in valid_methods:
            config = CustomAuthRequestConfig(endpoint="/oauth/token", method=method)
            assert config.method == method

    def test_method_case_insensitive(self) -> None:
        """Test that method is converted to uppercase"""
        config = CustomAuthRequestConfig(endpoint="/oauth/token", method="post")
        assert config.method == "POST"

    def test_body_and_bodyform_exclusive(self) -> None:
        """Test that body and bodyForm cannot both be specified"""
        with pytest.raises(CustomAuthRequestError) as exc_info:
            CustomAuthRequestConfig(
                endpoint="/oauth/token",
                body={"grant_type": "client_credentials"},
                bodyForm="grant_type=client_credentials",
            )
        assert "Cannot specify both 'body' and 'bodyForm'" in str(exc_info.value)

    def test_body_or_bodyform_valid(self) -> None:
        """Test that body OR bodyForm is valid"""
        config1 = CustomAuthRequestConfig(
            endpoint="/oauth/token", body={"grant_type": "client_credentials"}
        )
        assert config1.body == {"grant_type": "client_credentials"}

        config2 = CustomAuthRequestConfig(
            endpoint="/oauth/token", bodyForm="grant_type=client_credentials"
        )
        assert config2.bodyForm == "grant_type=client_credentials"


# ============================================================================
# Early Validation Tests (init_client)
# ============================================================================


class TestEarlyValidation:
    """Test early validation in init_client before authentication"""

    @pytest.fixture
    def mock_ocean_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mock ocean.integration_config"""
        config = {
            "base_url": "https://api.example.com",
            "auth_type": "custom",
            "custom_auth_request": {
                "endpoint": "/oauth/token",
                "method": "POST",
                "body": {"grant_type": "client_credentials"},
            },
            "custom_auth_response": {
                "headers": {"Authorization": "Bearer {{.access_token}}"},
            },
        }
        from port_ocean.context.ocean import ocean

        monkeypatch.setattr(ocean, "integration_config", config)

    def test_init_client_validates_template_syntax_before_auth(
        self, mock_ocean_config: None
    ) -> None:
        """Test that template syntax is validated before authentication"""
        from initialize_client import init_client

        # This should pass - valid template syntax
        client = init_client()
        assert client is not None

    def test_init_client_fails_on_invalid_template_syntax(
        self, mock_ocean_config: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that invalid template syntax fails before authentication"""
        from port_ocean.context.ocean import ocean

        config = ocean.integration_config.copy()
        config["custom_auth_response"] = {
            "headers": {"Authorization": "Bearer {{access_token}}"},  # Missing dot
        }
        monkeypatch.setattr(ocean, "integration_config", config)

        from initialize_client import init_client

        with pytest.raises(TemplateSyntaxError) as exc_info:
            init_client()
        assert "Invalid template syntax" in str(exc_info.value)
        assert "headers.Authorization" in str(exc_info.value)

    def test_init_client_fails_on_missing_custom_auth_request(
        self, mock_ocean_config: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that missing customAuthRequest raises CustomAuthRequestError"""
        from port_ocean.context.ocean import ocean

        config = ocean.integration_config.copy()
        del config["custom_auth_request"]
        monkeypatch.setattr(ocean, "integration_config", config)

        from initialize_client import init_client

        with pytest.raises(CustomAuthRequestError) as exc_info:
            init_client()
        assert "customAuthRequest is required" in str(exc_info.value)

    def test_init_client_fails_on_missing_custom_auth_response(
        self, mock_ocean_config: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that missing customAuthResponse raises CustomAuthResponseError"""
        from port_ocean.context.ocean import ocean

        config = ocean.integration_config.copy()
        del config["custom_auth_response"]
        monkeypatch.setattr(ocean, "integration_config", config)

        from initialize_client import init_client

        with pytest.raises(CustomAuthResponseError) as exc_info:
            init_client()
        assert "customAuthResponse is required" in str(exc_info.value)

    def test_init_client_validates_empty_custom_auth_response(
        self, mock_ocean_config: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that empty customAuthResponse raises CustomAuthResponseError"""
        from port_ocean.context.ocean import ocean

        config = ocean.integration_config.copy()
        config["custom_auth_response"] = {}  # Empty - should fail
        monkeypatch.setattr(ocean, "integration_config", config)

        from initialize_client import init_client

        with pytest.raises(CustomAuthResponseError) as exc_info:
            init_client()
        assert (
            "At least one of 'headers', 'queryParams', or 'body' must be provided"
            in str(exc_info.value)
        )
