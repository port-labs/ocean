import pytest
from unittest.mock import AsyncMock
from typing import Any, List

from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter
from base_client import BaseCheckmarxClient
from checkmarx_one.core.options import ListProjectOptions


class TestCheckmarxProjectExporter:
    """Test cases for CheckmarxProjectExporter."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock BaseCheckmarxClient for testing."""
        mock_client = AsyncMock(spec=BaseCheckmarxClient)
        mock_client._send_api_request = AsyncMock()

        # Create an async generator for _get_paginated_resources
        async def mock_paginated_resources(*args, **kwargs):
            # This will be set up in individual tests
            pass

        mock_client._get_paginated_resources = mock_paginated_resources
        return mock_client

    @pytest.fixture
    def project_exporter(self, mock_client: AsyncMock) -> CheckmarxProjectExporter:
        """Create a CheckmarxProjectExporter instance for testing."""
        return CheckmarxProjectExporter(mock_client)

    @pytest.fixture
    def sample_project(self) -> dict[str, Any]:
        """Sample project data for testing."""
        return {
            "id": "proj-123",
            "name": "Test Project",
            "description": "A test project",
            "status": "active",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
        }

    @pytest.fixture
    def sample_projects_batch(
        self, sample_project: dict[str, Any]
    ) -> List[dict[str, Any]]:
        """Sample batch of projects for testing."""
        return [
            sample_project,
            {
                "id": "proj-456",
                "name": "Another Project",
                "description": "Another test project",
                "status": "active",
                "createdAt": "2024-01-02T00:00:00Z",
                "updatedAt": "2024-01-02T00:00:00Z",
            },
        ]

    @pytest.mark.asyncio
    async def test_get_project_by_id_success(
        self,
        project_exporter: CheckmarxProjectExporter,
        mock_client: AsyncMock,
        sample_project: dict[str, Any],
    ) -> None:
        """Test successful project retrieval by ID."""
        mock_client._send_api_request.return_value = sample_project

        result = await project_exporter.get_project_by_id("proj-123")

        mock_client._send_api_request.assert_called_once_with("/projects/proj-123")
        assert result == sample_project

    @pytest.mark.asyncio
    async def test_get_project_by_id_with_different_ids(
        self, project_exporter: CheckmarxProjectExporter, mock_client: AsyncMock
    ) -> None:
        """Test project retrieval with different project IDs."""
        project_ids = ["proj-123", "proj-456", "proj-789"]

        for project_id in project_ids:
            mock_client._send_api_request.return_value = {"id": project_id}
            result = await project_exporter.get_project_by_id(project_id)

            mock_client._send_api_request.assert_called_with(f"/projects/{project_id}")
            assert result["id"] == project_id

    @pytest.mark.asyncio
    async def test_get_projects_without_parameters(
        self,
        project_exporter: CheckmarxProjectExporter,
        mock_client: AsyncMock,
        sample_projects_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting projects without any parameters."""

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_projects_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        list_options = ListProjectOptions()
        async for batch in project_exporter.get_projects(list_options):
            results.append(batch)

        assert len(results) == 1
        assert results[0] == sample_projects_batch

    @pytest.mark.asyncio
    async def test_get_projects_with_limit(
        self,
        project_exporter: CheckmarxProjectExporter,
        mock_client: AsyncMock,
        sample_projects_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting projects with limit parameter."""

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_projects_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        list_options = ListProjectOptions(limit=50)
        async for batch in project_exporter.get_projects(list_options):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_projects_with_offset(
        self,
        project_exporter: CheckmarxProjectExporter,
        mock_client: AsyncMock,
        sample_projects_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting projects with offset parameter."""

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_projects_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        list_options = ListProjectOptions(offset=100)
        async for batch in project_exporter.get_projects(list_options):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_projects_with_limit_and_offset(
        self,
        project_exporter: CheckmarxProjectExporter,
        mock_client: AsyncMock,
        sample_projects_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting projects with both limit and offset parameters."""

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_projects_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        list_options = ListProjectOptions(limit=25, offset=50)
        async for batch in project_exporter.get_projects(list_options):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_projects_multiple_batches(
        self,
        project_exporter: CheckmarxProjectExporter,
        mock_client: AsyncMock,
        sample_projects_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting projects with multiple batches."""
        batch1 = sample_projects_batch[:1]
        batch2 = sample_projects_batch[1:]

        async def mock_paginated_resources(*args, **kwargs):
            yield batch1
            yield batch2

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        list_options = ListProjectOptions()
        async for batch in project_exporter.get_projects(list_options):
            results.append(batch)

        assert len(results) == 2
        assert results[0] == batch1
        assert results[1] == batch2

    @pytest.mark.asyncio
    async def test_get_projects_empty_result(
        self, project_exporter: CheckmarxProjectExporter, mock_client: AsyncMock
    ) -> None:
        """Test getting projects with empty result."""

        async def mock_paginated_resources(*args, **kwargs):
            # Yield nothing - empty result
            if False:  # This ensures it's an async generator
                yield []

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        list_options = ListProjectOptions()
        async for batch in project_exporter.get_projects(list_options):
            results.append(batch)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_project_by_id_exception_handling(
        self, project_exporter: CheckmarxProjectExporter, mock_client: AsyncMock
    ) -> None:
        """Test exception handling in get_project_by_id."""
        mock_client._send_api_request.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            await project_exporter.get_project_by_id("proj-123")

    @pytest.mark.asyncio
    async def test_get_projects_exception_handling(
        self, project_exporter: CheckmarxProjectExporter, mock_client: AsyncMock
    ) -> None:
        """Test exception handling in get_projects."""

        async def mock_paginated_resources(*args, **kwargs):
            if True:  # This ensures it's an async generator
                raise Exception("Pagination Error")
            yield []

        mock_client._get_paginated_resources = mock_paginated_resources

        with pytest.raises(Exception, match="Pagination Error"):
            list_options = ListProjectOptions()
            async for batch in project_exporter.get_projects(list_options):
                pass

    def test_project_exporter_inheritance(
        self, project_exporter: CheckmarxProjectExporter
    ) -> None:
        """Test that CheckmarxProjectExporter properly inherits from AbstractCheckmarxExporter."""
        from checkmarx_one.core.exporters.abstract_exporter import (
            AbstractCheckmarxExporter,
        )

        assert isinstance(project_exporter, AbstractCheckmarxExporter)

    def test_project_exporter_docstring(self) -> None:
        """Test that CheckmarxProjectExporter has proper documentation."""
        assert CheckmarxProjectExporter.__doc__ is not None
        assert "Exporter for Checkmarx One projects" in CheckmarxProjectExporter.__doc__

    def test_get_project_by_id_docstring(self) -> None:
        """Test that get_project_by_id method has proper documentation."""
        assert CheckmarxProjectExporter.get_project_by_id.__doc__ is not None
        assert (
            "Get a specific project by ID"
            in CheckmarxProjectExporter.get_project_by_id.__doc__
        )

    def test_get_projects_docstring(self) -> None:
        """Test that get_projects method has proper documentation."""
        assert CheckmarxProjectExporter.get_projects.__doc__ is not None
        assert (
            "Get projects from Checkmarx One"
            in CheckmarxProjectExporter.get_projects.__doc__
        )
