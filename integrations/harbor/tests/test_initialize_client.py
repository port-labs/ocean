"""Unit tests for Harbor client initialization."""

from unittest.mock import MagicMock, patch

import pytest

from harbor.client import HarborClient
from initialize_client import create_harbor_client


def test_create_harbor_client_with_basic_auth() -> None:
    """Test creating HarborClient with basic authentication."""
    with patch("initialize_client.ocean") as mock_ocean:
        # Use MagicMock, not AsyncMock - these are sync calls
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "verify_ssl": True,
            "auth_type": "basic",
            "username": "admin",
            "password": "password123",
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client = create_harbor_client()

        assert isinstance(client, HarborClient)
        assert client.base_url == "https://harbor.example.com"
        assert client.client.verify is True


def test_create_harbor_client_without_auth() -> None:
    """Test creating HarborClient without authentication."""
    with patch("initialize_client.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "verify_ssl": False,
            "auth_type": "none",
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client = create_harbor_client()

        assert isinstance(client, HarborClient)
        assert client.base_url == "https://harbor.example.com"
        assert client.client.verify is False


def test_create_harbor_client_default_verify_ssl() -> None:
    """Test creating HarborClient with default verify_ssl setting."""
    with patch("initialize_client.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "auth_type": "none",
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client = create_harbor_client()

        assert isinstance(client, HarborClient)
        # Default should be False
        assert client.client.verify is False


def test_create_harbor_client_with_partial_credentials() -> None:
    """Test creating HarborClient with basic auth but missing credentials."""
    with patch("initialize_client.ocean") as mock_ocean:
        # Missing password
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://harbor.example.com",
            "verify_ssl": False,
            "auth_type": "basic",
            "username": "admin",
            "password": None,
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client = create_harbor_client()

        assert isinstance(client, HarborClient)
        # Should initialize without auth since credentials are incomplete
        assert client.client.auth is None


def test_create_harbor_client_integration() -> None:
    """Integration test for create_harbor_client with realistic config."""
    with patch("initialize_client.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(side_effect=lambda key, default=None: {
            "base_url": "https://registry.harbor.io",
            "verify_ssl": True,
            "auth_type": "basic",
            "username": "test_user",
            "password": "test_pass",
            "pageSize": 50,
        }.get(key, default))
        mock_ocean.integration_config = mock_config

        client = create_harbor_client()

        assert isinstance(client, HarborClient)
        assert client.base_url == "https://registry.harbor.io"
        assert client.client.auth is not None

