import pytest
from unittest.mock import patch, MagicMock

from checkmarx_one.client_factory import (
    create_checkmarx_client,
    create_project_exporter,
    create_scan_exporter
)
from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter
from checkmarx_one.core.exporters.scan_exporter import CheckmarxScanExporter
from client import CheckmarxClient


class TestClientFactory:
    @patch('checkmarx_one.client_factory.init_client')
    def test_create_checkmarx_client(self, mock_init_client):
        """Test create_checkmarx_client factory function."""
        # Arrange
        mock_client = MagicMock(spec=CheckmarxClient)
        mock_init_client.return_value = mock_client

        # Act
        result = create_checkmarx_client()

        # Assert
        assert result is mock_client
        mock_init_client.assert_called_once()

    @patch('checkmarx_one.client_factory.create_checkmarx_client')
    def test_create_project_exporter(self, mock_create_client):
        """Test create_project_exporter factory function."""
        # Arrange
        mock_client = MagicMock(spec=CheckmarxClient)
        mock_create_client.return_value = mock_client

        # Act
        result = create_project_exporter()

        # Assert
        assert isinstance(result, CheckmarxProjectExporter)
        assert result.client is mock_client
        mock_create_client.assert_called_once()

    @patch('checkmarx_one.client_factory.create_checkmarx_client')
    def test_create_scan_exporter(self, mock_create_client):
        """Test create_scan_exporter factory function."""
        # Arrange
        mock_client = MagicMock(spec=CheckmarxClient)
        mock_create_client.return_value = mock_client

        # Act
        result = create_scan_exporter()

        # Assert
        assert isinstance(result, CheckmarxScanExporter)
        assert result.client is mock_client
        mock_create_client.assert_called_once()

    @patch('checkmarx_one.client_factory.init_client')
    def test_create_project_exporter_with_real_client_creation(self, mock_init_client):
        """Test create_project_exporter with actual client creation flow."""
        # Arrange
        mock_client = MagicMock(spec=CheckmarxClient)
        mock_init_client.return_value = mock_client

        # Act
        exporter = create_project_exporter()

        # Assert
        assert isinstance(exporter, CheckmarxProjectExporter)
        assert exporter.client is mock_client
        mock_init_client.assert_called_once()

    @patch('checkmarx_one.client_factory.init_client')
    def test_create_scan_exporter_with_real_client_creation(self, mock_init_client):
        """Test create_scan_exporter with actual client creation flow."""
        # Arrange
        mock_client = MagicMock(spec=CheckmarxClient)
        mock_init_client.return_value = mock_client

        # Act
        exporter = create_scan_exporter()

        # Assert
        assert isinstance(exporter, CheckmarxScanExporter)
        assert exporter.client is mock_client
        mock_init_client.assert_called_once()

    @patch('checkmarx_one.client_factory.init_client')
    def test_factory_functions_create_independent_instances(self, mock_init_client):
        """Test that factory functions create independent instances."""
        # Arrange
        mock_client1 = MagicMock(spec=CheckmarxClient)
        mock_client2 = MagicMock(spec=CheckmarxClient)
        mock_init_client.side_effect = [mock_client1, mock_client2]

        # Act
        exporter1 = create_project_exporter()
        exporter2 = create_scan_exporter()

        # Assert
        assert exporter1.client is mock_client1
        assert exporter2.client is mock_client2
        assert exporter1.client is not exporter2.client
        assert mock_init_client.call_count == 2

    @patch('checkmarx_one.client_factory.init_client')
    def test_multiple_calls_create_new_instances(self, mock_init_client):
        """Test that multiple calls to factory functions create new instances."""
        # Arrange
        mock_client1 = MagicMock(spec=CheckmarxClient)
        mock_client2 = MagicMock(spec=CheckmarxClient)
        mock_init_client.side_effect = [mock_client1, mock_client2]

        # Act
        exporter1 = create_project_exporter()
        exporter2 = create_project_exporter()

        # Assert
        assert isinstance(exporter1, CheckmarxProjectExporter)
        assert isinstance(exporter2, CheckmarxProjectExporter)
        assert exporter1 is not exporter2
        assert exporter1.client is not exporter2.client
        assert mock_init_client.call_count == 2

    @patch('checkmarx_one.client_factory.init_client')
    def test_factory_propagates_client_initialization_errors(self, mock_init_client):
        """Test that factory functions propagate client initialization errors."""
        # Arrange
        mock_init_client.side_effect = Exception("Client initialization failed")

        # Act & Assert
        with pytest.raises(Exception, match="Client initialization failed"):
            create_checkmarx_client()

        with pytest.raises(Exception, match="Client initialization failed"):
            create_project_exporter()

        with pytest.raises(Exception, match="Client initialization failed"):
            create_scan_exporter()
