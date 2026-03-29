import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, AsyncIterator, List
import types

from checkmarx_one.core.options import ListScanOptions, SingleScanOptions

# Mock port_ocean imports before importing the module under test
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
        list_options = ListScanOptions(project_names=["proj-1", "proj-2"])
        async for batch in scan_exporter.get_paginated_resources(list_options):
            results.append(batch)

        assert len(results) == 1
        assert results[0] == sample_scans_batch
        assert call_args["endpoint"] == "/scans"
        assert call_args["object_key"] == "scans"
        assert call_args["params"]["project-names"] == ["proj-1", "proj-2"]

    @pytest.mark.asyncio
    async def test_get_scans_with_project_id_filter(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
        sample_scans_batch: List[dict[str, Any]],
    ) -> None:
        """Test that project_id_filter is wired to the project-id query param."""

        call_args: dict[str, Any] = {}

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            call_args["params"] = params
            yield sample_scans_batch

        mock_client.send_paginated_request = mock_paginated_resources

        list_options = ListScanOptions(project_id_filter="proj-abc")
        results: List[List[dict[str, Any]]] = []
        async for batch in scan_exporter.get_paginated_resources(list_options):
            results.append(batch)

        assert call_args["params"]["project-id"] == "proj-abc"

    @pytest.mark.asyncio
    async def test_latest_scans_only_dedup(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
    ) -> None:
        """latest_scans_only=True should yield only the first scan per (projectId, branch) group."""

        scans_page1 = [
            {"id": "scan-1", "projectId": "proj-A", "branch": "main", "status": "Completed"},
            {"id": "scan-2", "projectId": "proj-A", "branch": "develop", "status": "Completed"},
        ]
        scans_page2 = [
            # Duplicate group (proj-A, main) — should be skipped
            {"id": "scan-3", "projectId": "proj-A", "branch": "main", "status": "Completed"},
            # New group
            {"id": "scan-4", "projectId": "proj-B", "branch": "main", "status": "Completed"},
        ]

        call_params: dict[str, Any] = {}

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            call_params.update(params or {})
            yield scans_page1
            yield scans_page2

        mock_client.send_paginated_request = mock_paginated_resources

        list_options = ListScanOptions(latest_scans_only=True)
        all_batches: List[List[dict[str, Any]]] = []
        async for batch in scan_exporter.get_paginated_resources(list_options):
            all_batches.append(batch)

        # API should receive sort and statuses params
        assert call_params.get("sort") == "-created_at"
        assert call_params.get("statuses") == ["Completed"]

        all_scans = [s for batch in all_batches for s in batch]
        scan_ids = [s["id"] for s in all_scans]

        assert "scan-1" in scan_ids
        assert "scan-2" in scan_ids
        assert "scan-3" not in scan_ids, "scan-3 duplicates (proj-A, main) and must be dropped"
        assert "scan-4" in scan_ids

    @pytest.mark.asyncio
    async def test_latest_scans_only_false_no_dedup(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
    ) -> None:
        """latest_scans_only=False (default) should yield all scans without dedup."""

        scans = [
            {"id": "scan-1", "projectId": "proj-A", "branch": "main"},
            {"id": "scan-2", "projectId": "proj-A", "branch": "main"},
        ]

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield scans

        mock_client.send_paginated_request = mock_paginated_resources

        list_options = ListScanOptions()
        all_batches: List[List[dict[str, Any]]] = []
        async for batch in scan_exporter.get_paginated_resources(list_options):
            all_batches.append(batch)

        all_scans = [s for batch in all_batches for s in batch]
        assert len(all_scans) == 2

    @pytest.mark.asyncio
    async def test_get_previous_completed_scan_found(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
    ) -> None:
        """get_previous_completed_scan returns the first non-current scan from the API."""

        current_scan_id = "scan-new"
        prev_scan = {"id": "scan-prev", "projectId": "proj-A", "branch": "main", "status": "Completed"}

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            # Simulate newest-first order: current first, then previous
            yield [{"id": current_scan_id, "projectId": "proj-A", "branch": "main"}, prev_scan]

        mock_client.send_paginated_request = mock_paginated_resources

        result = await scan_exporter.get_previous_completed_scan("proj-A", "main", current_scan_id)
        assert result is not None
        assert result["id"] == "scan-prev"

    @pytest.mark.asyncio
    async def test_get_previous_completed_scan_not_found(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
    ) -> None:
        """get_previous_completed_scan returns None when no prior scan exists."""

        current_scan_id = "scan-only"

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield [{"id": current_scan_id}]

        mock_client.send_paginated_request = mock_paginated_resources

        result = await scan_exporter.get_previous_completed_scan("proj-A", "main", current_scan_id)
        assert result is None
