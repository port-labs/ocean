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
    from checkmarx_one.core.exporters.application_exporter import (
        CheckmarxApplicationExporter,
    )
from checkmarx_one.core.options import ListApplicationOptions, SingleApplicationOptions


class TestCheckmarxApplicationExporter:
    """Test cases for CheckmarxApplicationExporter."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock CheckmarxOneClient for testing."""
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
    def application_exporter(
        self, mock_client: AsyncMock
    ) -> CheckmarxApplicationExporter:
        """Create a CheckmarxApplicationExporter instance for testing."""
        return CheckmarxApplicationExporter(mock_client)

    @pytest.fixture
    def sample_application(self) -> dict[str, Any]:
        """Sample application data for testing."""
        return {
            "id": "app-123",
            "name": "Test Application",
            "description": "A test application",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
            "criticality": 3,
            "rules": [],
            "tags": {"env": "test"},
        }

    @pytest.fixture
    def sample_applications_batch(
        self, sample_application: dict[str, Any]
    ) -> List[dict[str, Any]]:
        """Sample batch of applications for testing."""
        return [
            sample_application,
            {
                "id": "app-456",
                "name": "Another Application",
                "description": "Another test application",
                "createdAt": "2024-01-02T00:00:00Z",
                "updatedAt": "2024-01-02T00:00:00Z",
                "criticality": 2,
                "rules": [],
                "tags": {},
            },
        ]

    @pytest.fixture
    def sample_projects_batch(self) -> List[dict[str, Any]]:
        """Sample batch of projects associated with an application."""
        return [
            {
                "id": "proj-123",
                "name": "Project 1",
                "applicationIds": ["app-123"],
            },
            {
                "id": "proj-456",
                "name": "Project 2",
                "applicationIds": ["app-123"],
            },
        ]

    @pytest.mark.asyncio
    async def test_get_application_by_id_success(
        self,
        application_exporter: CheckmarxApplicationExporter,
        mock_client: AsyncMock,
        sample_application: dict[str, Any],
    ) -> None:
        """Test successful application retrieval by ID."""
        mock_client.send_api_request.return_value = sample_application

        result = await application_exporter.get_resource(
            SingleApplicationOptions(application_id="app-123")
        )

        mock_client.send_api_request.assert_called_once_with("/applications/app-123")
        assert result == sample_application

    @pytest.mark.asyncio
    async def test_get_applications_without_parameters(
        self,
        application_exporter: CheckmarxApplicationExporter,
        mock_client: AsyncMock,
        sample_applications_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting applications without any parameters."""

        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield sample_applications_batch

        mock_client.send_paginated_request = mock_paginated_resources

        results = []
        list_options = ListApplicationOptions()
        async for batch in application_exporter.get_paginated_resources(list_options):
            results.append(batch)

        assert len(results) == 1
        assert results[0] == sample_applications_batch

    @pytest.mark.asyncio
    async def test_get_application_by_id_exception_handling(
        self, application_exporter: CheckmarxApplicationExporter, mock_client: AsyncMock
    ) -> None:
        """Test exception handling in get_resource."""
        mock_client.send_api_request.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            await application_exporter.get_resource(
                SingleApplicationOptions(application_id="app-123")
            )

    @pytest.mark.asyncio
    async def test_get_application_projects_success(
        self,
        application_exporter: CheckmarxApplicationExporter,
        mock_client: AsyncMock,
        sample_projects_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting projects for an application."""

        async def mock_paginated_resources(
            endpoint: str, object_key: str
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield sample_projects_batch

        mock_client.send_paginated_request = mock_paginated_resources

        results = []
        async for batch in application_exporter.get_application_projects("app-123"):
            results.append(batch)

        assert len(results) == 1
        assert results[0] == sample_projects_batch
