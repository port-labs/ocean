from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, Mock

import pytest

from harbor.clients.http.client import HarborClient
from harbor.core.exporters.repository_exporter import HarborRepositoryExporter


class TestHarborRepositoryExporter:
    """Test cases for HarborRepositoryExporter."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create a mock Harbor client."""
        return Mock(spec=HarborClient)

    @pytest.fixture
    def exporter(self, mock_client: Any) -> HarborRepositoryExporter:
        """Create a test exporter instance."""
        return HarborRepositoryExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_paginated_resources_yields_repository_batches(
        self, exporter: HarborRepositoryExporter, mock_client: Any
    ) -> None:
        """Test get_paginated_resources yields batches of repositories."""
        mock_repos: List[Dict[str, Any]] = [
            {"id": 1, "name": "repo1", "project_name": "test"},
            {"id": 2, "name": "repo2", "project_name": "test"},
        ]

        async def mock_paginated_request(
            endpoint: str, params: Dict[str, Any]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield mock_repos

        object.__setattr__(mock_client, "send_paginated_request", mock_paginated_request)

        options = {"project_name": "test"}
        repos: List[Dict[str, Any]] = []
        async for batch in exporter.get_paginated_resources(options):
            repos.extend(batch)

        assert len(repos) == 2
        assert repos[0]["name"] == "repo1"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_raises_error_when_project_name_missing(
        self, exporter: HarborRepositoryExporter, mock_client: Any
    ) -> None:
        """Test get_paginated_resources raises ValueError when project_name missing."""
        with pytest.raises(ValueError, match="project_name is required"):
            async for _ in exporter.get_paginated_resources({}):
                pass

    @pytest.mark.asyncio
    async def test_get_resource_returns_single_repository(
        self, exporter: HarborRepositoryExporter, mock_client: Any
    ) -> None:
        """Test get_resource returns a single repository."""
        mock_repo = {"id": 1, "name": "test_repo"}

        mock_client.get_repository = AsyncMock(return_value=mock_repo)

        repo = await exporter.get_resource("test_project", "test_repo")

        assert repo == mock_repo
        mock_client.get_repository.assert_called_once_with("test_project", "test_repo")

    @pytest.mark.asyncio
    async def test_get_resource_returns_none_when_repository_not_found(
        self, exporter: HarborRepositoryExporter, mock_client: Any
    ) -> None:
        """Test get_resource returns None when repository doesn't exist."""
        mock_client.get_repository = AsyncMock(return_value=None)

        repo = await exporter.get_resource("test_project", "nonexistent")

        assert repo is None
