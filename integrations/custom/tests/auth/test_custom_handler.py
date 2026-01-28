"""Tests for CustomAuth handler class"""

import pytest
import httpx
from typing import Dict, Any
from unittest.mock import MagicMock

from http_server.auth.custom_handler import CustomAuth


@pytest.mark.asyncio
class TestCustomAuthHandler:
    """Test CustomAuth handler"""

    @pytest.fixture
    def mock_client(self) -> httpx.AsyncClient:
        """Mock httpx AsyncClient"""
        return MagicMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def config(self) -> Dict[str, Any]:
        """Test configuration"""
        return {
            "base_url": "https://api.example.com",
            "verify_ssl": True,
            "custom_auth_request": {
                "endpoint": "/oauth/token",
                "method": "POST",
                "body": {"grant_type": "client_credentials"},
            },
            "custom_auth_request_template": {
                "headers": {"Authorization": "Bearer {{.access_token}}"},
            },
        }

    def test_init_creates_auth_flow_manager(
        self, mock_client: httpx.AsyncClient, config: Dict[str, Any]
    ) -> None:
        """Test that CustomAuth initializes with AuthFlowManager"""
        handler = CustomAuth(mock_client, config)

        assert handler.client == mock_client
        assert handler.config == config
        assert handler.custom_auth is not None
        # Verify it's an AuthFlowManager instance
        from http_server.auth.custom.auth_flow import AuthFlowManager

        assert isinstance(handler.custom_auth, AuthFlowManager)

    def test_setup_sets_client_auth(
        self, mock_client: httpx.AsyncClient, config: Dict[str, Any]
    ) -> None:
        """Test that setup() sets the client's auth attribute"""
        handler = CustomAuth(mock_client, config)
        handler.setup()

        assert mock_client.auth == handler.custom_auth

    def test_init_validates_config(self, mock_client: httpx.AsyncClient) -> None:
        """Test that invalid config raises appropriate errors"""
        invalid_config = {
            "base_url": "https://api.example.com",
            "custom_auth_request": {
                "endpoint": "/oauth/token",
                "method": "INVALID",  # Invalid method
            },
        }

        from http_server.exceptions import CustomAuthRequestError

        with pytest.raises(CustomAuthRequestError):
            CustomAuth(mock_client, invalid_config)
