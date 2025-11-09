from typing import Any
from unittest.mock import MagicMock, patch

from utils import init_terraform_client


class TestInitTerraformClient:
    @patch("utils.ocean")
    @patch("utils.TerraformClient")
    def test_init_terraform_client_success(
        self, mock_terraform_client_class: Any, mock_ocean: Any
    ) -> None:
        mock_config = {
            "terraform_cloud_host": "https://app.terraform.io",
            "terraform_cloud_token": "test-token-123",
        }
        mock_ocean.integration_config = mock_config

        init_terraform_client()

        mock_terraform_client_class.assert_called_once_with(
            "https://app.terraform.io", "test-token-123"
        )

    @patch("utils.ocean")
    @patch("utils.TerraformClient")
    def test_init_terraform_client_returns_instance(
        self, mock_terraform_client_class: Any, mock_ocean: Any
    ) -> None:
        mock_config = {
            "terraform_cloud_host": "https://custom.terraform.io",
            "terraform_cloud_token": "custom-token",
        }
        mock_ocean.integration_config = mock_config
        mock_instance = MagicMock()
        mock_terraform_client_class.return_value = mock_instance

        result = init_terraform_client()

        assert result == mock_instance

    @patch("utils.ocean")
    @patch("utils.TerraformClient")
    def test_init_terraform_client_with_different_hosts(
        self, mock_terraform_client_class: Any, mock_ocean: Any
    ) -> None:
        configs = [
            {
                "terraform_cloud_host": "https://terraform.example.com",
                "terraform_cloud_token": "token1",
            },
            {
                "terraform_cloud_host": "https://app.terraform.io",
                "terraform_cloud_token": "token2",
            },
        ]

        for config in configs:
            mock_ocean.integration_config = config
            init_terraform_client()

        assert mock_terraform_client_class.call_count == len(configs)
