"""Simple standalone tests for Checkmarx One integration components."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from utils import ObjectKind


class TestObjectKindSimple:
    def test_enum_basic_functionality(self):
        """Test basic enum functionality."""
        assert ObjectKind.PROJECT == "project"
        assert ObjectKind.SCAN == "scan"
        assert str(ObjectKind.PROJECT) == "project"
        assert str(ObjectKind.SCAN) == "scan"

    def test_enum_members(self):
        """Test enum has expected members."""
        members = list(ObjectKind)
        assert len(members) == 2
        assert ObjectKind.PROJECT in members
        assert ObjectKind.SCAN in members

    def test_enum_values(self):
        """Test enum values."""
        assert ObjectKind.PROJECT.value == "project"
        assert ObjectKind.SCAN.value == "scan"


class TestClientFactoryMocked:
    @patch('checkmarx_one.client_factory.init_client')
    def test_create_checkmarx_client_mocked(self, mock_init):
        """Test client factory with mocked dependencies."""
        from checkmarx_one.client_factory import create_checkmarx_client

        mock_client = MagicMock()
        mock_init.return_value = mock_client

        result = create_checkmarx_client()

        assert result is mock_client
        mock_init.assert_called_once()

    @patch('checkmarx_one.client_factory.create_checkmarx_client')
    def test_create_project_exporter_mocked(self, mock_create_client):
        """Test project exporter creation with mocked client."""
        from checkmarx_one.client_factory import create_project_exporter
        from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        result = create_project_exporter()

        assert isinstance(result, CheckmarxProjectExporter)
        assert result.client is mock_client


class TestExportersMocked:
    def test_project_exporter_initialization(self):
        """Test project exporter can be initialized."""
        from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter

        mock_client = MagicMock()
        exporter = CheckmarxProjectExporter(mock_client)

        assert exporter.client is mock_client

    def test_scan_exporter_initialization(self):
        """Test scan exporter can be initialized."""
        from checkmarx_one.core.exporters.scan_exporter import CheckmarxScanExporter

        mock_client = MagicMock()
        exporter = CheckmarxScanExporter(mock_client)

        assert exporter.client is mock_client

    @pytest.mark.asyncio
    async def test_project_exporter_get_resource(self):
        """Test project exporter get_resource method."""
        from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter

        mock_client = AsyncMock()
        mock_client.get_project_by_id.return_value = {"id": "test-proj", "name": "Test"}

        exporter = CheckmarxProjectExporter(mock_client)
        result = await exporter.get_resource({"project_id": "test-proj"})

        assert result == {"id": "test-proj", "name": "Test"}
        mock_client.get_project_by_id.assert_called_once_with("test-proj")

    @pytest.mark.asyncio
    async def test_scan_exporter_get_resource(self):
        """Test scan exporter get_resource method."""
        from checkmarx_one.core.exporters.scan_exporter import CheckmarxScanExporter

        mock_client = AsyncMock()
        mock_client.get_scan_by_id.return_value = {"id": "test-scan", "projectId": "proj-1"}

        exporter = CheckmarxScanExporter(mock_client)
        result = await exporter.get_resource({"scan_id": "test-scan"})

        assert result == {"id": "test-scan", "projectId": "proj-1"}
        mock_client.get_scan_by_id.assert_called_once_with("test-scan")


class TestOptionTypes:
    def test_project_options_types(self):
        """Test project options type definitions."""
        from checkmarx_one.core.options import ListProjectOptions, SingleProjectOptions

        # Test that we can create option dictionaries
        list_options: ListProjectOptions = {"limit": 10, "offset": 0}
        single_options: SingleProjectOptions = {"project_id": "test-id"}

        assert list_options["limit"] == 10
        assert single_options["project_id"] == "test-id"

    def test_scan_options_types(self):
        """Test scan options type definitions."""
        from checkmarx_one.core.options import ListScanOptions, SingleScanOptions

        # Test that we can create option dictionaries
        list_options: ListScanOptions = {"project_id": "proj-1", "limit": 25}
        single_options: SingleScanOptions = {"scan_id": "scan-id"}

        assert list_options["project_id"] == "proj-1"
        assert single_options["scan_id"] == "scan-id"


class TestAbstractExporter:
    def test_abstract_exporter_properties(self):
        """Test abstract exporter class properties."""
        from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
        from abc import ABC

        assert issubclass(AbstractCheckmarxExporter, ABC)
        assert hasattr(AbstractCheckmarxExporter, '__abstractmethods__')

        # Should have abstract methods
        abstract_methods = AbstractCheckmarxExporter.__abstractmethods__
        assert "get_resource" in abstract_methods
        assert "get_paginated_resources" in abstract_methods

    def test_concrete_exporter_implements_abstract(self):
        """Test that concrete exporters implement the abstract interface."""
        from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter
        from checkmarx_one.core.exporters.scan_exporter import CheckmarxScanExporter
        from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter

        assert issubclass(CheckmarxProjectExporter, AbstractCheckmarxExporter)
        assert issubclass(CheckmarxScanExporter, AbstractCheckmarxExporter)

        # Should be able to instantiate
        mock_client = MagicMock()
        project_exporter = CheckmarxProjectExporter(mock_client)
        scan_exporter = CheckmarxScanExporter(mock_client)

        assert isinstance(project_exporter, AbstractCheckmarxExporter)
        assert isinstance(scan_exporter, AbstractCheckmarxExporter)
