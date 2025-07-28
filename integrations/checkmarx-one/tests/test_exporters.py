import pytest
from unittest.mock import AsyncMock, MagicMock

from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter
from checkmarx_one.core.exporters.scan_exporter import CheckmarxScanExporter
from checkmarx_one.core.options import ListProjectOptions, SingleProjectOptions, ListScanOptions, SingleScanOptions


class TestCheckmarxProjectExporter:
    @pytest.fixture
    def mock_client(self):
        """Mock CheckmarxClient for testing."""
        return AsyncMock()

    @pytest.fixture
    def project_exporter(self, mock_client):
        """Create CheckmarxProjectExporter instance."""
        return CheckmarxProjectExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_resource_single_project(self, project_exporter, mock_client):
        """Test getting a single project by ID."""
        # Arrange
        project_id = "proj-123"
        mock_project = {"id": project_id, "name": "Test Project", "status": "active"}
        mock_client.get_project_by_id.return_value = mock_project

        options: SingleProjectOptions = {"project_id": project_id}

        # Act
        result = await project_exporter.get_resource(options)

        # Assert
        assert result == mock_project
        mock_client.get_project_by_id.assert_called_once_with(project_id)

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_options(self, project_exporter, mock_client):
        """Test getting paginated projects with limit and offset options."""
        # Arrange
        mock_projects = [{"id": "proj-1", "name": "Project 1"}]

        async def mock_get_projects(*args, **kwargs):
            yield mock_projects

        mock_client.get_projects = mock_get_projects

        options: ListProjectOptions = {"limit": 50, "offset": 100}

        # Act
        results = []
        async for batch in project_exporter.get_paginated_resources(options):
            results.extend(batch)

        # Assert
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_paginated_resources_empty_response(self, project_exporter, mock_client):
        """Test getting paginated projects with empty response."""
        # Arrange
        async def mock_get_projects(*args, **kwargs):
            # No yields - empty async generator
            return
            yield  # Unreachable, makes it an async generator

        mock_client.get_projects = mock_get_projects

        # Act
        results = []
        async for batch in project_exporter.get_paginated_resources():
            results.extend(batch)

        # Assert
        assert results == []

    @pytest.mark.asyncio
    async def test_get_paginated_resources_partial_options(self, project_exporter, mock_client):
        """Test getting paginated projects with partial options."""
        # Arrange
        mock_projects = [{"id": "proj-1", "name": "Project 1"}]

        async def mock_get_projects(*args, **kwargs):
            yield mock_projects

        mock_client.get_projects = mock_get_projects

        options: ListProjectOptions = {"limit": 25}  # Only limit, no offset

        # Act
        results = []
        async for batch in project_exporter.get_paginated_resources(options):
            results.extend(batch)

        # Assert
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_inheritance_from_abstract_exporter(self, project_exporter):
        """Test that project exporter properly inherits from abstract base."""
        from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter

        assert isinstance(project_exporter, AbstractCheckmarxExporter)
        assert hasattr(project_exporter, 'client')
        assert hasattr(project_exporter, 'get_resource')
        assert hasattr(project_exporter, 'get_paginated_resources')


class TestCheckmarxScanExporter:
    @pytest.fixture
    def mock_client(self):
        """Mock CheckmarxClient for testing."""
        return AsyncMock()

    @pytest.fixture
    def scan_exporter(self, mock_client):
        """Create CheckmarxScanExporter instance."""
        return CheckmarxScanExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_resource_single_scan(self, scan_exporter, mock_client):
        """Test getting a single scan by ID."""
        # Arrange
        scan_id = "scan-456"
        mock_scan = {"id": scan_id, "projectId": "proj-123", "status": "completed"}
        mock_client.get_scan_by_id.return_value = mock_scan

        options: SingleScanOptions = {"scan_id": scan_id}

        # Act
        result = await scan_exporter.get_resource(options)

        # Assert
        assert result == mock_scan
        mock_client.get_scan_by_id.assert_called_once_with(scan_id)

    @pytest.mark.asyncio
    async def test_get_paginated_resources_no_options(self, scan_exporter, mock_client):
        """Test getting paginated scans with no options."""
        # Arrange
        mock_scans_batch1 = [
            {"id": "scan-1", "projectId": "proj-1"},
            {"id": "scan-2", "projectId": "proj-1"}
        ]
        mock_scans_batch2 = [
            {"id": "scan-3", "projectId": "proj-2"}
        ]

        async def mock_get_scans(*args, **kwargs):
            yield mock_scans_batch1
            yield mock_scans_batch2

        mock_client.get_scans = mock_get_scans

        # Act
        results = []
        async for batch in scan_exporter.get_paginated_resources():
            results.extend(batch)

        # Assert
        assert len(results) == 3
        assert results[0] == {"id": "scan-1", "projectId": "proj-1"}
        assert results[2] == {"id": "scan-3", "projectId": "proj-2"}

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_project_filter(self, scan_exporter, mock_client):
        """Test getting paginated scans filtered by project ID."""
        # Arrange
        mock_scans = [{"id": "scan-1", "projectId": "proj-123"}]

        async def mock_get_scans(*args, **kwargs):
            yield mock_scans

        mock_client.get_scans = mock_get_scans

        options: ListScanOptions = {"project_id": "proj-123"}

        # Act
        results = []
        async for batch in scan_exporter.get_paginated_resources(options):
            results.extend(batch)

        # Assert
        assert len(results) == 1
        assert results[0]["projectId"] == "proj-123"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_all_options(self, scan_exporter, mock_client):
        """Test getting paginated scans with all options."""
        # Arrange
        mock_scans = [{"id": "scan-1", "projectId": "proj-123"}]

        async def mock_get_scans(*args, **kwargs):
            yield mock_scans

        mock_client.get_scans = mock_get_scans

        options: ListScanOptions = {
            "project_id": "proj-123",
            "limit": 25,
            "offset": 50
        }

        # Act
        results = []
        async for batch in scan_exporter.get_paginated_resources(options):
            results.extend(batch)

        # Assert
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_paginated_resources_empty_response(self, scan_exporter, mock_client):
        """Test getting paginated scans with empty response."""
        # Arrange
        async def mock_get_scans(*args, **kwargs):
            # No yields - empty async generator
            return
            yield  # Unreachable, makes it an async generator

        mock_client.get_scans = mock_get_scans

        # Act
        results = []
        async for batch in scan_exporter.get_paginated_resources():
            results.extend(batch)

        # Assert
        assert results == []

    @pytest.mark.asyncio
    async def test_get_paginated_resources_limit_only(self, scan_exporter, mock_client):
        """Test getting paginated scans with limit only."""
        # Arrange
        mock_scans = [{"id": "scan-1", "projectId": "proj-1"}]

        async def mock_get_scans(*args, **kwargs):
            yield mock_scans

        mock_client.get_scans = mock_get_scans

        options: ListScanOptions = {"limit": 10}

        # Act
        results = []
        async for batch in scan_exporter.get_paginated_resources(options):
            results.extend(batch)

        # Assert
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_paginated_resources_offset_only(self, scan_exporter, mock_client):
        """Test getting paginated scans with offset only."""
        # Arrange
        mock_scans = [{"id": "scan-1", "projectId": "proj-1"}]

        async def mock_get_scans(*args, **kwargs):
            yield mock_scans

        mock_client.get_scans = mock_get_scans

        options: ListScanOptions = {"offset": 20}

        # Act
        results = []
        async for batch in scan_exporter.get_paginated_resources(options):
            results.extend(batch)

        # Assert
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_inheritance_from_abstract_exporter(self, scan_exporter):
        """Test that scan exporter properly inherits from abstract base."""
        from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter

        assert isinstance(scan_exporter, AbstractCheckmarxExporter)
        assert hasattr(scan_exporter, 'client')
        assert hasattr(scan_exporter, 'get_resource')
        assert hasattr(scan_exporter, 'get_paginated_resources')
