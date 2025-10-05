"""Tests for HTTP Server client"""

import pytest
from http_server.client import HttpServerClient


class TestHttpServerClient:
    """Test cases for HttpServerClient"""

    def test_client_initialization_no_auth(self) -> None:
        """Test client can be initialized with no authentication"""
        client = HttpServerClient(
            base_url="http://localhost:8080",
            auth_type="none",
            auth_config={},
            pagination_config={},
        )
        assert client.base_url == "http://localhost:8080"
        assert client.auth_type == "none"

    def test_client_with_bearer_auth(self) -> None:
        """Test client initialization with bearer token auth"""
        client = HttpServerClient(
            base_url="http://localhost:8080",
            auth_type="bearer_token",
            auth_config={"api_token": "test-token"},
            pagination_config={},
        )
        assert client.auth_type == "bearer_token"

    def test_client_with_basic_auth(self) -> None:
        """Test client initialization with basic auth"""
        client = HttpServerClient(
            base_url="http://localhost:8080",
            auth_type="basic",
            auth_config={"username": "user", "password": "pass"},
            pagination_config={},
        )
        assert client.auth_type == "basic"

    def test_client_with_api_key_auth(self) -> None:
        """Test client initialization with API key auth"""
        client = HttpServerClient(
            base_url="http://localhost:8080",
            auth_type="api_key",
            auth_config={"api_key": "test-key"},
            pagination_config={},
        )
        assert client.auth_type == "api_key"