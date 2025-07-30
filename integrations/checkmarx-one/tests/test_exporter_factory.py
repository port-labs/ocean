import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from checkmarx_one.exporter_factory import (
    create_checkmarx_client,
    create_project_exporter,
    create_scan_exporter,
)
from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter
from checkmarx_one.core.exporters.scan_exporter import CheckmarxScanExporter
from client import CheckmarxClient


class TestExporterFactory:
    """Test cases for exporter factory functions."""

    @pytest.fixture
    def mock_checkmarx_client(self) -> MagicMock:
        """Create a mock CheckmarxClient for testing."""
        return MagicMock(spec=CheckmarxClient)

    @pytest.fixture
    def mock_project_exporter(self) -> MagicMock:
        """Create a mock CheckmarxProjectExporter for testing."""
        return MagicMock(spec=CheckmarxProjectExporter)

    @pytest.fixture
    def mock_scan_exporter(self) -> MagicMock:
        """Create a mock CheckmarxScanExporter for testing."""
        return MagicMock(spec=CheckmarxScanExporter)

    @patch('checkmarx_one.exporter_factory.init_client')
    def test_create_checkmarx_client(self, mock_init_client: MagicMock, mock_checkmarx_client: MagicMock) -> None:
        """Test that create_checkmarx_client calls init_client and returns the result."""
        mock_init_client.return_value = mock_checkmarx_client

        result = create_checkmarx_client()

        mock_init_client.assert_called_once()
        assert result == mock_checkmarx_client

    @patch('checkmarx_one.exporter_factory.init_client')
    def test_create_project_exporter(self, mock_init_client: MagicMock, mock_checkmarx_client: MagicMock) -> None:
        """Test that create_project_exporter creates a project exporter with initialized client."""
        mock_init_client.return_value = mock_checkmarx_client

        result = create_project_exporter()

        mock_init_client.assert_called_once()
        assert isinstance(result, CheckmarxProjectExporter)
        assert result.client == mock_checkmarx_client

    @patch('checkmarx_one.exporter_factory.init_client')
    def test_create_scan_exporter(self, mock_init_client: MagicMock, mock_checkmarx_client: MagicMock) -> None:
        """Test that create_scan_exporter creates a scan exporter with initialized client."""
        mock_init_client.return_value = mock_checkmarx_client

        result = create_scan_exporter()

        mock_init_client.assert_called_once()
        assert isinstance(result, CheckmarxScanExporter)
        assert result.client == mock_checkmarx_client

    @patch('checkmarx_one.exporter_factory.init_client')
    def test_factory_functions_return_different_instances(self, mock_init_client: MagicMock, mock_checkmarx_client: MagicMock) -> None:
        """Test that factory functions return different instances of exporters."""
        mock_init_client.return_value = mock_checkmarx_client

        project_exporter_1 = create_project_exporter()
        project_exporter_2 = create_project_exporter()

        # Should be different instances
        assert project_exporter_1 is not project_exporter_2
        # But should have the same client
        assert project_exporter_1.client == project_exporter_2.client

    @patch('checkmarx_one.exporter_factory.init_client')
    def test_factory_functions_with_different_clients(self, mock_init_client: MagicMock) -> None:
        """Test that factory functions work with different client instances."""
        mock_client_1 = MagicMock(spec=CheckmarxClient)
        mock_client_2 = MagicMock(spec=CheckmarxClient)

        # Set up mock to return different clients on subsequent calls
        mock_init_client.side_effect = [mock_client_1, mock_client_2]

        project_exporter = create_project_exporter()
        scan_exporter = create_scan_exporter()

        assert project_exporter.client == mock_client_1
        assert scan_exporter.client == mock_client_2

    def test_create_checkmarx_client_docstring(self) -> None:
        """Test that create_checkmarx_client has proper documentation."""
        assert create_checkmarx_client.__doc__ is not None
        assert "Create and return a configured Checkmarx One client" in create_checkmarx_client.__doc__

    def test_create_project_exporter_docstring(self) -> None:
        """Test that create_project_exporter has proper documentation."""
        assert create_project_exporter.__doc__ is not None
        assert "Create a project exporter with initialized client" in create_project_exporter.__doc__

    def test_create_scan_exporter_docstring(self) -> None:
        """Test that create_scan_exporter has proper documentation."""
        assert create_scan_exporter.__doc__ is not None
        assert "Create a scan exporter with initialized client" in create_scan_exporter.__doc__

    @patch('checkmarx_one.exporter_factory.init_client')
    def test_factory_functions_call_init_client_once(self, mock_init_client: MagicMock, mock_checkmarx_client: MagicMock) -> None:
        """Test that each factory function calls init_client exactly once."""
        mock_init_client.return_value = mock_checkmarx_client

        create_project_exporter()
        create_scan_exporter()

        # Should be called twice total (once for each exporter)
        assert mock_init_client.call_count == 2

    @patch('checkmarx_one.exporter_factory.init_client')
    def test_factory_functions_with_exception_handling(self, mock_init_client: MagicMock) -> None:
        """Test that factory functions properly handle exceptions from init_client."""
        mock_init_client.side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            create_project_exporter()

        with pytest.raises(Exception, match="Connection failed"):
            create_scan_exporter()

    @patch('checkmarx_one.exporter_factory.init_client')
    def test_factory_functions_return_correct_types(self, mock_init_client: MagicMock, mock_checkmarx_client: MagicMock) -> None:
        """Test that factory functions return the correct types."""
        mock_init_client.return_value = mock_checkmarx_client

        project_exporter = create_project_exporter()
        scan_exporter = create_scan_exporter()

        assert isinstance(project_exporter, CheckmarxProjectExporter)
        assert isinstance(scan_exporter, CheckmarxScanExporter)
        assert isinstance(project_exporter.client, CheckmarxClient)
        assert isinstance(scan_exporter.client, CheckmarxClient)
