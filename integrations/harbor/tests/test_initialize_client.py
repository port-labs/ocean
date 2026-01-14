"""Unit tests for Harbor client initialization."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from harbor.clients.client_factory import HarborClientFactory
from harbor.clients.http.client import HarborClient


@pytest.fixture(autouse=True)
def reset_client_between_tests() -> Generator[None, None, None]:
    """Reset the singleton client before each test to ensure test isolation."""
    HarborClientFactory.reset_client()
    yield
    HarborClientFactory.reset_client()


def test_get_harbor_client_singleton() -> None:
    """Test that HarborClientFactory.get_client returns the same instance (singleton pattern)."""
    with patch("harbor.clients.client_factory.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "username": "test_user",
            "password": "test_password",
            "api_version": "v2.0",
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client1 = HarborClientFactory.get_client()
        client2 = HarborClientFactory.get_client()

        # Should return the same instance
        assert client1 is client2


def test_reset_harbor_client() -> None:
    """Test that HarborClientFactory.reset_client creates a new instance on next call."""
    with patch("harbor.clients.client_factory.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "username": "test_user",
            "password": "test_password",
            "api_version": "v2.0",
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client1 = HarborClientFactory.get_client()
        HarborClientFactory.reset_client()
        client2 = HarborClientFactory.get_client()

        # Should be different instances after reset
        assert client1 is not client2


def test_create_harbor_client_with_basic_auth() -> None:
    """Test creating HarborClient with basic authentication."""
    with patch("harbor.clients.client_factory.ocean") as mock_ocean:
        # Use MagicMock, not AsyncMock - these are sync calls
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "username": "admin",
            "password": "password123",
            "api_version": "v2.0",
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client = HarborClientFactory.get_client()

        assert isinstance(client, HarborClient)
        assert client.base_url == "https://harbor.example.com"
        assert client.username == "admin"
        assert client.password == "password123"


def test_create_harbor_client_without_auth() -> None:
    """Test that HarborClient creation fails when authentication is missing."""
    with patch("harbor.clients.client_factory.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            # Missing username and password
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        # Should raise MissingIntegrationCredentialException because username is required
        from harbor.helpers.exceptions import MissingIntegrationCredentialException
        with pytest.raises(MissingIntegrationCredentialException, match="username is required"):
            HarborClientFactory.get_client()


def test_create_harbor_client_default_api_version() -> None:
    """Test creating HarborClient with default api_version setting."""
    with patch("harbor.clients.client_factory.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "username": "test_user",
            "password": "test_password",
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client = HarborClientFactory.get_client()

        assert isinstance(client, HarborClient)
        # Default should be v2.0
        assert client.api_version == "v2.0"


def test_create_harbor_client_with_partial_credentials() -> None:
    """Test that HarborClient creation fails with partial credentials."""
    with patch("harbor.clients.client_factory.ocean") as mock_ocean:
        # Missing password
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "username": "admin",
            "password": None,  # Missing password
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        # Should raise MissingIntegrationCredentialException because password is required
        from harbor.helpers.exceptions import MissingIntegrationCredentialException
        with pytest.raises(MissingIntegrationCredentialException, match="password is required"):
            HarborClientFactory.get_client()


def test_create_harbor_client_integration() -> None:
    """Integration test for HarborClientFactory with realistic config."""
    with patch("harbor.clients.client_factory.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://registry.harbor.io",
            "username": "test_user",
            "password": "test_pass",
            "api_version": "v2.0",
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client = HarborClientFactory.get_client()

        assert isinstance(client, HarborClient)
        assert client.base_url == "https://registry.harbor.io"
        assert client.username == "test_user"
        assert client.password == "test_pass"

