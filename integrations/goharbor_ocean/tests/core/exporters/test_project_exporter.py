from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, Mock

import pytest

from harbor.clients.http.client import HarborClient
from harbor.core.exporters.project_exporter import HarborProjectExporter


class TestHarborProjectExporter:
    """Test cases for HarborProjectExporter."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create a mock Harbor client."""
        return Mock(spec=HarborClient)

    @pytest.fixture
    def exporter(self, mock_client: Any) -> HarborProjectExporter:
        """Create a test exporter instance."""
        return HarborProjectExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_paginated_resources_yields_project_batches(
        self, exporter: HarborProjectExporter, mock_client: Any
    ) -> None:
        """Test get_paginated_resources yields batches of projects."""
        mock_projects: List[Dict[str, Any]] = [
            {"project_id": 1, "name": "project1"},
            {"project_id": 2, "name": "project2"},
        ]

        async def mock_paginated_request(
            endpoint: str, params: Dict[str, Any]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield mock_projects

        object.__setattr__(mock_client, "send_paginated_request", mock_paginated_request)

        projects: List[Dict[str, Any]] = []
        async for batch in exporter.get_paginated_resources({}):
            projects.extend(batch)

        assert len(projects) == 2
        assert projects[0]["name"] == "project1"
        assert projects[1]["name"] == "project2"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_passes_query_parameters(
        self, exporter: HarborProjectExporter, mock_client: Any
    ) -> None:
        """Test get_paginated_resources passes query parameters to client."""
        received_params = None

        async def mock_paginated_request(
            endpoint: str, params: Dict[str, Any]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            nonlocal received_params
            received_params = params
            yield []

        object.__setattr__(mock_client, "send_paginated_request", mock_paginated_request)

        options = {"q": "test", "sort": "name"}
        async for _ in exporter.get_paginated_resources(options):
            pass

        assert received_params == {"q": "test", "sort": "name"}

    @pytest.mark.asyncio
    async def test_get_resource_returns_single_project(self, exporter: HarborProjectExporter, mock_client: Any) -> None:
        """Test get_resource returns a single project by name."""
        mock_project = {"project_id": 1, "name": "test_project"}

        mock_client.get_project = AsyncMock(return_value=mock_project)

        project = await exporter.get_resource("test_project")

        assert project == mock_project
        mock_client.get_project.assert_called_once_with("test_project")

    @pytest.mark.asyncio
    async def test_get_resource_returns_none_when_project_not_found(
        self, exporter: HarborProjectExporter, mock_client: Any
    ) -> None:
        """Test get_resource returns None when project doesn't exist."""
        mock_client.get_project = AsyncMock(return_value=None)

        project = await exporter.get_resource("nonexistent")

        assert project is None
