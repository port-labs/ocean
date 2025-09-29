import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, AsyncIterator, List

# Mock port_ocean imports before importing the module under test
with patch.dict(
    "sys.modules",
    {
        "port_ocean.core.ocean_types": MagicMock(),
        "port_ocean.core.integrations.base": MagicMock(),
        "port_ocean.utils.cache": MagicMock(),
    },
):
    from checkmarx_one.clients.client import CheckmarxOneClient
    from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter
from checkmarx_one.core.options import ListProjectOptions, SingleProjectOptions


class TestCheckmarxProjectExporter:
    """Test cases for CheckmarxProjectExporter."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock BaseCheckmarxClient for testing."""
        mock_client = AsyncMock(spec=CheckmarxOneClient)
        mock_client._send_api_request = AsyncMock()

        # Create an async generator for _get_paginated_resources
        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[List[dict[str, Any]]]:
            if False:  # ensure async generator type
                yield []

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
        mock_client.send_api_request.return_value = sample_project

        result = await project_exporter.get_resource(
            SingleProjectOptions(project_id="proj-123")
        )

        mock_client.send_api_request.assert_called_once_with("/projects/proj-123")
        assert result == sample_project

    @pytest.mark.asyncio
    async def test_get_projects_without_parameters(
        self,
        project_exporter: CheckmarxProjectExporter,
        mock_client: AsyncMock,
        sample_projects_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting projects without any parameters."""

        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield sample_projects_batch

        mock_client.send_paginated_request = mock_paginated_resources

        results = []
        list_options = ListProjectOptions()
        async for batch in project_exporter.get_paginated_resources(list_options):
            results.append(batch)

        assert len(results) == 1
        assert results[0] == sample_projects_batch

    @pytest.mark.asyncio
    async def test_get_project_by_id_exception_handling(
        self, project_exporter: CheckmarxProjectExporter, mock_client: AsyncMock
    ) -> None:
        """Test exception handling in get_project_by_id."""
        mock_client.send_api_request.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            await project_exporter.get_resource(
                SingleProjectOptions(project_id="proj-123")
            )
