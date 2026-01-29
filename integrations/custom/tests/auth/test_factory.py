from typing import Dict, Any
import pytest
import httpx
from http_server.auth.factory import get_auth_handler
from http_server.auth.api_key import ApiKeyAuth
from http_server.auth.basic import BasicAuth
from http_server.auth.bearer_token import BearerTokenAuth
from http_server.auth.custom import CustomAuth
from http_server.auth.no_auth import NoAuth


@pytest.mark.asyncio
class TestFactory:
    """Test factory for authentication handlers"""

    @pytest.fixture
    def mock_client(self) -> httpx.AsyncClient:
        """Mock httpx.AsyncClient"""
        return httpx.AsyncClient()

    @pytest.fixture
    def config(self) -> Dict[str, Any]:
        """Mock config"""
        return {
            "custom_auth_request": {
                "endpoint": "/oauth/token",
                "method": "POST",
                "body": {"grant_type": "client_credentials"},
            },
            "custom_auth_request_template": {
                "headers": {"Authorization": "Bearer {{.access_token}}"},
            },
        }

    def test_get_auth_handler_custom(
        self, mock_client: httpx.AsyncClient, config: Dict[str, Any]
    ) -> None:
        """Test getting custom authentication handler"""
        handler = get_auth_handler("custom", mock_client, config)
        assert isinstance(handler, CustomAuth)

    def test_get_auth_handler_bearer_token(
        self, mock_client: httpx.AsyncClient, config: Dict[str, Any]
    ) -> None:
        """Test getting bearer token authentication handler"""
        handler = get_auth_handler("bearer_token", mock_client, {})
        assert isinstance(handler, BearerTokenAuth)

    def test_get_auth_handler_api_key(
        self, mock_client: httpx.AsyncClient, config: Dict[str, Any]
    ) -> None:
        """Test getting API key authentication handler"""
        handler = get_auth_handler("api_key", mock_client, {})
        assert isinstance(handler, ApiKeyAuth)

    def test_get_auth_handler_basic(
        self, mock_client: httpx.AsyncClient, config: Dict[str, Any]
    ) -> None:
        """Test getting basic authentication handler"""
        handler = get_auth_handler("basic", mock_client, {})
        assert isinstance(handler, BasicAuth)

    def test_get_auth_handler_none(
        self, mock_client: httpx.AsyncClient, config: Dict[str, Any]
    ) -> None:
        """Test getting none authentication handler"""
        handler = get_auth_handler("none", mock_client, {})
        assert isinstance(handler, NoAuth)
