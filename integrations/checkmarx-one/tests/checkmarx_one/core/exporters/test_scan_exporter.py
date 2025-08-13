import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, AsyncIterator, List
import types

from checkmarx_one.core.options import ListScanOptions, SingleScanOptions

# Mock port_ocean imports before importing the module under test
# Provide a no-op decorator for cache_iterator_result so decorated methods keep behavior/docstrings
cache_module = types.ModuleType("port_ocean.utils.cache")


def _noop_cache_iterator_result(*_args: Any, **_kwargs: Any) -> Any:
    def _decorator(func: Any) -> Any:
        return func

    return _decorator


setattr(cache_module, "cache_iterator_result", _noop_cache_iterator_result)

with patch.dict(
    "sys.modules",
    {
        "port_ocean.core.ocean_types": MagicMock(),
        "port_ocean.core.integrations.base": MagicMock(),
        "port_ocean.utils.cache": cache_module,
    },
):
    from checkmarx_one.clients.client import CheckmarxOneClient
    from checkmarx_one.core.exporters.scan_exporter import CheckmarxScanExporter


class TestCheckmarxScanExporter:
    """Test cases for CheckmarxScanExporter."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock CheckmarxOneClient for testing."""
        mock_client = AsyncMock(spec=CheckmarxOneClient)
        mock_client.send_api_request = AsyncMock()

        # Create an async generator placeholder for send_paginated_request
        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[List[dict[str, Any]]]:
            if False:  # ensure async generator type
                yield []

        mock_client.send_paginated_request = mock_paginated_resources
        return mock_client

    @pytest.fixture
    def scan_exporter(self, mock_client: AsyncMock) -> CheckmarxScanExporter:
        """Create a CheckmarxScanExporter instance for testing."""
        return CheckmarxScanExporter(mock_client)

    @pytest.fixture
    def sample_scan(self) -> dict[str, Any]:
        """Sample scan data for testing."""
        return {
            "id": "scan-123",
            "status": "Completed",
            "projectId": "proj-123",
            "createdAt": "2024-01-01T00:00:00Z",
        }

    @pytest.fixture
    def sample_scans_batch(self, sample_scan: dict[str, Any]) -> List[dict[str, Any]]:
        """Sample batch of scans for testing."""
        return [
            sample_scan,
            {
                "id": "scan-456",
                "status": "Running",
                "projectId": "proj-456",
                "createdAt": "2024-01-02T00:00:00Z",
            },
        ]

    @pytest.mark.asyncio
    async def test_get_scan_by_id_success(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
        sample_scan: dict[str, Any],
    ) -> None:
        """Test successful scan retrieval by ID."""
        mock_client.send_api_request.return_value = sample_scan

        result = await scan_exporter.get_resource(SingleScanOptions(scan_id="scan-123"))

        mock_client.send_api_request.assert_called_once_with("/scans/scan-123")
        assert result == sample_scan

    @pytest.mark.asyncio
    async def test_get_scans_without_parameters(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
        sample_scans_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scans without any parameters."""

        call_args: dict[str, Any] = {}

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            call_args["endpoint"] = endpoint
            call_args["object_key"] = object_key
            call_args["params"] = params
            yield sample_scans_batch

        mock_client.send_paginated_request = mock_paginated_resources

        results: List[List[dict[str, Any]]] = []
        list_options = ListScanOptions()
        async for batch in scan_exporter.get_paginated_resources(list_options):
            results.append(batch)

        assert len(results) == 1
        assert results[0] == sample_scans_batch
        assert call_args["endpoint"] == "/scans"
        assert call_args["object_key"] == "scans"
        assert call_args["params"] == {}

    @pytest.mark.asyncio
    async def test_get_scans_with_project_ids(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
        sample_scans_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scans filtered by project IDs."""

        call_args: dict[str, Any] = {}

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            call_args["endpoint"] = endpoint
            call_args["object_key"] = object_key
            call_args["params"] = params
            yield sample_scans_batch

        mock_client.send_paginated_request = mock_paginated_resources

        results: List[List[dict[str, Any]]] = []
        list_options = ListScanOptions(project_ids=["proj-1", "proj-2"])
        async for batch in scan_exporter.get_paginated_resources(list_options):
            results.append(batch)

        assert len(results) == 1
        assert results[0] == sample_scans_batch
        assert call_args["endpoint"] == "/scans"
        assert call_args["object_key"] == "scans"
        assert call_args["params"]["project-ids"] == "proj-1,proj-2"

    @pytest.mark.asyncio
    async def test_get_scans_multiple_batches(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
        sample_scans_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scans with multiple batches."""
        batch1 = sample_scans_batch[:1]
        batch2 = sample_scans_batch[1:]

        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield batch1
            yield batch2

        mock_client.send_paginated_request = mock_paginated_resources

        results: List[List[dict[str, Any]]] = []
        list_options = ListScanOptions()
        async for batch in scan_exporter.get_paginated_resources(list_options):
            results.append(batch)

        assert len(results) == 2
        assert results[0] == batch1
        assert results[1] == batch2

    @pytest.mark.asyncio
    async def test_get_scans_empty_result(
        self, scan_exporter: CheckmarxScanExporter, mock_client: AsyncMock
    ) -> None:
        """Test getting scans with empty result."""

        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[List[dict[str, Any]]]:
            if False:  # ensure async generator type
                yield []

        mock_client.send_paginated_request = mock_paginated_resources

        results: List[List[dict[str, Any]]] = []
        list_options = ListScanOptions()
        async for batch in scan_exporter.get_paginated_resources(list_options):
            results.append(batch)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_scan_by_id_exception_handling(
        self, scan_exporter: CheckmarxScanExporter, mock_client: AsyncMock
    ) -> None:
        """Test exception handling in get_scan_by_id."""
        mock_client.send_api_request.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            await scan_exporter.get_resource(SingleScanOptions(scan_id="scan-123"))

    def test_scan_exporter_inheritance(
        self, scan_exporter: CheckmarxScanExporter
    ) -> None:
        """Test that CheckmarxScanExporter properly inherits from AbstractCheckmarxExporter."""
        assert hasattr(scan_exporter, "client")
        assert hasattr(scan_exporter, "get_resource")
        assert hasattr(scan_exporter, "get_paginated_resources")

    def test_scan_exporter_docstring(self) -> None:
        """Test that CheckmarxScanExporter has proper documentation."""
        assert CheckmarxScanExporter.__doc__ is not None
        assert "Exporter for Checkmarx One scans" in CheckmarxScanExporter.__doc__

    def test_get_resource_docstring(self) -> None:
        """Test that get_resource method has proper documentation."""
        assert CheckmarxScanExporter.get_resource.__doc__ is not None
        assert "Get a specific scan by ID" in CheckmarxScanExporter.get_resource.__doc__

    def test_get_paginated_resources_docstring(self) -> None:
        """Test that get_paginated_resources method has proper documentation."""
        assert CheckmarxScanExporter.get_paginated_resources.__doc__ is not None
        assert (
            "Get scans from Checkmarx One"
            in CheckmarxScanExporter.get_paginated_resources.__doc__
        )
