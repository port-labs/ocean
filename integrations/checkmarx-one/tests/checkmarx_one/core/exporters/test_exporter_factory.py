import pytest
from unittest.mock import patch, MagicMock

# Mock port_ocean imports before importing the module under test
with patch.dict(
    "sys.modules",
    {
        "port_ocean.core.ocean_types": MagicMock(),
        "port_ocean.core.integrations.base": MagicMock(),
        "port_ocean.utils.cache": MagicMock(),
    },
):
    from checkmarx_one.exporter_factory import (
        create_project_exporter,
        create_scan_exporter,
        create_scan_result_exporter,
    )
    from checkmarx_one.clients.client import CheckmarxOneClient
    from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter
    from checkmarx_one.core.exporters.scan_exporter import CheckmarxScanExporter
    from checkmarx_one.core.exporters.scan_result_exporter import (
        CheckmarxScanResultExporter,
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
    def test_factory_functions_return_different_instances(
        self, mock_get_client: MagicMock
    ) -> None:
        """Test that factory functions return different instances."""
        mock_client = MagicMock(spec=CheckmarxOneClient)
        mock_get_client.return_value = mock_client

        project_exporter = create_project_exporter()
        scan_exporter = create_scan_exporter()
        scan_result_exporter = create_scan_result_exporter()

        assert project_exporter is not scan_exporter
        assert project_exporter is not scan_result_exporter
        assert scan_exporter is not scan_result_exporter

    @patch("checkmarx_one.exporter_factory.get_checkmarx_client")
    def test_factory_functions_with_different_clients(
        self, mock_get_client: MagicMock
    ) -> None:
        """Test that factory functions work with different clients."""
        mock_client1 = MagicMock(spec=CheckmarxOneClient)
        mock_client2 = MagicMock(spec=CheckmarxOneClient)
        mock_client3 = MagicMock(spec=CheckmarxOneClient)

        # Reset the mock to return different clients on subsequent calls
        mock_get_client.side_effect = [mock_client1, mock_client2, mock_client3]

        project_exporter = create_project_exporter()
        scan_exporter = create_scan_exporter()
        scan_result_exporter = create_scan_result_exporter()

        assert project_exporter.client == mock_client1
        assert scan_exporter.client == mock_client2
        assert scan_result_exporter.client == mock_client3

    def test_create_project_exporter_docstring(self) -> None:
        """Test that create_project_exporter has proper documentation."""
        assert create_project_exporter.__doc__ is not None
        assert "Create a project exporter" in create_project_exporter.__doc__

    def test_create_scan_exporter_docstring(self) -> None:
        """Test that create_scan_exporter has proper documentation."""
        assert create_scan_exporter.__doc__ is not None
        assert "Create a scan exporter" in create_scan_exporter.__doc__

    @patch("checkmarx_one.exporter_factory.get_checkmarx_client")
    def test_factory_functions_call_init_client_once(
        self, mock_get_client: MagicMock
    ) -> None:
        """Test that each factory function calls get_checkmarx_client exactly once."""
        mock_client = MagicMock(spec=CheckmarxOneClient)
        mock_get_client.return_value = mock_client

        create_project_exporter()
        create_scan_exporter()
        create_scan_result_exporter()

        assert mock_get_client.call_count == 3

    @patch("checkmarx_one.exporter_factory.get_checkmarx_client")
    def test_factory_functions_with_exception_handling(
        self, mock_get_client: MagicMock
    ) -> None:
        """Test that factory functions handle exceptions properly."""
        mock_get_client.side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            create_project_exporter()

        with pytest.raises(Exception, match="Connection failed"):
            create_scan_exporter()

        with pytest.raises(Exception, match="Connection failed"):
            create_scan_result_exporter()

    @patch("checkmarx_one.exporter_factory.get_checkmarx_client")
    def test_factory_functions_return_correct_types(
        self, mock_get_client: MagicMock
    ) -> None:
        """Test that factory functions return correct types."""
        mock_client = MagicMock(spec=CheckmarxOneClient)
        mock_get_client.return_value = mock_client

        project_exporter = create_project_exporter()
        scan_exporter = create_scan_exporter()
        scan_result_exporter = create_scan_result_exporter()

        assert isinstance(project_exporter, CheckmarxProjectExporter)
        assert isinstance(scan_exporter, CheckmarxScanExporter)
        assert isinstance(scan_result_exporter, CheckmarxScanResultExporter)
