from unittest.mock import MagicMock, patch

import pytest

from harbor.clients.client_factory import HarborClientFactory
from harbor.clients.http.client import HarborClient


class TestHarborClientFactory:
    """Test cases for HarborClientFactory singleton pattern."""

    def test_get_client_returns_harbor_client_instance(self) -> None:
        """Test get_client returns HarborClient instance."""
        with patch("port_ocean.context.ocean.ocean") as mock_ocean:
            mock_ocean.integration_config = {
                "harbor_url": "https://harbor.example.com",
                "harbor_username": "test_user",
                "harbor_password": "test_pass",
            }

            client = HarborClientFactory.get_client()

            assert isinstance(client, HarborClient)
            assert client._base_url_raw == "https://harbor.example.com"

    def test_get_client_returns_same_instance_on_multiple_calls(self) -> None:
        """Test get_client returns same singleton instance."""
        with patch("port_ocean.context.ocean.ocean") as mock_ocean:
            mock_ocean.integration_config = {
                "harbor_url": "https://harbor.example.com",
                "harbor_username": "test_user",
                "harbor_password": "test_pass",
            }

            client1 = HarborClientFactory.get_client()
            client2 = HarborClientFactory.get_client()

            assert client1 is client2

    def test_get_client_raises_value_error_when_harbor_url_missing(self) -> None:
        """Test get_client raises ValueError when harbor_url is missing."""
        with patch("port_ocean.context.ocean.ocean") as mock_ocean:
            mock_ocean.integration_config = {
                "harbor_username": "test_user",
                "harbor_password": "test_pass",
            }

            with pytest.raises(ValueError, match="harbor_url is required"):
                HarborClientFactory.get_client()

    def test_get_client_raises_value_error_when_harbor_username_missing(
        self,
    ) -> None:
        """Test get_client raises ValueError when harbor_username is missing."""
        with patch("port_ocean.context.ocean.ocean") as mock_ocean:
            mock_ocean.integration_config = {
                "harbor_url": "https://harbor.example.com",
                "harbor_password": "test_pass",
            }

            with pytest.raises(ValueError, match="harbor_username is required"):
                HarborClientFactory.get_client()

    def test_get_client_raises_value_error_when_harbor_password_missing(
        self,
    ) -> None:
        """Test get_client raises ValueError when harbor_password is missing."""
        with patch("port_ocean.context.ocean.ocean") as mock_ocean:
            mock_ocean.integration_config = {
                "harbor_url": "https://harbor.example.com",
                "harbor_username": "test_user",
            }

            with pytest.raises(ValueError, match="harbor_password is required"):
                HarborClientFactory.get_client()

    def test_reset_client_clears_singleton_instance(self) -> None:
        """Test reset_client clears the singleton instance."""
        with patch("port_ocean.context.ocean.ocean") as mock_ocean:
            mock_ocean.integration_config = {
                "harbor_url": "https://harbor.example.com",
                "harbor_username": "test_user",
                "harbor_password": "test_pass",
            }

            client1 = HarborClientFactory.get_client()
            # HarborClientFactory.reset_client()
            client2 = HarborClientFactory.get_client()

            assert client1 is not client2
