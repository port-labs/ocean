from unittest.mock import patch, MagicMock

from checkmarx_one.clients.client import CheckmarxOneClient
from checkmarx_one.core.exporters.api_sec_exporter import CheckmarxApiSecExporter
from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter
from checkmarx_one.core.exporters.scan_exporter import CheckmarxScanExporter
from checkmarx_one.exporter_factory import (
    create_api_sec_exporter,
    create_project_exporter,
    create_scan_exporter,
)


class TestExporterFactory:
    """Test cases for exporter factory functions."""

    @patch("checkmarx_one.exporter_factory.get_checkmarx_client")
    def test_create_project_exporter(self, mock_get_client: MagicMock) -> None:
        """Test creating a project exporter."""
        mock_client = MagicMock(spec=CheckmarxOneClient)
        mock_get_client.return_value = mock_client

        result = create_project_exporter()

        assert isinstance(result, CheckmarxProjectExporter)
        assert result.client == mock_client
        mock_get_client.assert_called_once()

    @patch("checkmarx_one.exporter_factory.get_checkmarx_client")
    def test_create_scan_exporter(self, mock_get_client: MagicMock) -> None:
        """Test creating a scan exporter."""
        mock_client = MagicMock(spec=CheckmarxOneClient)
        mock_get_client.return_value = mock_client

        result = create_scan_exporter()

        assert isinstance(result, CheckmarxScanExporter)
        assert result.client == mock_client
        mock_get_client.assert_called_once()

    @patch("checkmarx_one.exporter_factory.get_checkmarx_client")
    def test_create_api_sec_exporter(self, mock_get_client: MagicMock) -> None:
        """Test creating an API security exporter."""
        mock_client = MagicMock(spec=CheckmarxOneClient)
        mock_get_client.return_value = mock_client

        result = create_api_sec_exporter()

        assert isinstance(result, CheckmarxApiSecExporter)
        assert result.client == mock_client
        mock_get_client.assert_called_once()
