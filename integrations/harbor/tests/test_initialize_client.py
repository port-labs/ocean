"""Unit tests for Harbor client initialization."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from httpx import BasicAuth

from harbor.client import HarborClient
from initialize_client import get_harbor_client, reset_harbor_client


@pytest.fixture(autouse=True)
def reset_client_between_tests() -> Generator[None, None, None]:
    """Reset the singleton client before each test to ensure test isolation."""
    reset_harbor_client()
    yield
    reset_harbor_client()


def test_get_harbor_client_singleton() -> None:
    """Test that get_harbor_client returns the same instance (singleton pattern)."""
    with patch("initialize_client.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "verify_ssl": False,
            "username": "test_user",
            "password": "test_password",
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client1 = get_harbor_client()
        client2 = get_harbor_client()

        # Should return the same instance
        assert client1 is client2


def test_reset_harbor_client() -> None:
    """Test that reset_harbor_client creates a new instance on next call."""
    with patch("initialize_client.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "verify_ssl": False,
            "username": "test_user",
            "password": "test_password",
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client1 = get_harbor_client()
        reset_harbor_client()
        client2 = get_harbor_client()

        # Should be different instances after reset
        assert client1 is not client2


def test_create_harbor_client_with_basic_auth() -> None:
    """Test creating HarborClient with basic authentication."""
    with patch("initialize_client.ocean") as mock_ocean:
        # Use MagicMock, not AsyncMock - these are sync calls
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "verify_ssl": True,
            "username": "admin",
            "password": "password123",
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client = get_harbor_client()

        assert isinstance(client, HarborClient)
        assert client.base_url == "https://harbor.example.com"
        assert client.verify_ssl is True


def test_create_harbor_client_without_auth() -> None:
    """Test that HarborClient creation fails when authentication is missing."""
    with patch("initialize_client.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "verify_ssl": False,
            # Missing username and password
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        # Should raise ValueError because username is required
        with pytest.raises(ValueError, match="Username is required"):
            get_harbor_client()


def test_create_harbor_client_default_verify_ssl() -> None:
    """Test creating HarborClient with default verify_ssl setting."""
    with patch("initialize_client.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "username": "test_user",
            "password": "test_password",
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client = get_harbor_client()

        assert isinstance(client, HarborClient)
        # Default should be False
        assert client.verify_ssl is False


def test_create_harbor_client_with_partial_credentials() -> None:
    """Test that HarborClient creation fails with partial credentials."""
    with patch("initialize_client.ocean") as mock_ocean:
        # Missing password
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "verify_ssl": False,
            "username": "admin",
            "password": None,  # Missing password
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        # Should raise ValueError because password is required
        with pytest.raises(ValueError, match="Password is required"):
            get_harbor_client()


def test_create_harbor_client_integration() -> None:
    """Integration test for create_harbor_client with realistic config."""
    with patch("initialize_client.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://registry.harbor.io",
            "verify_ssl": True,
            "username": "test_user",
            "password": "test_pass",
            "pageSize": 50,
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client = get_harbor_client()

        assert isinstance(client, HarborClient)
        assert client.base_url == "https://registry.harbor.io"
        assert client._auth is not None
        assert isinstance(client._auth, BasicAuth)

