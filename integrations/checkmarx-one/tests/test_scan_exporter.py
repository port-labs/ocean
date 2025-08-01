import pytest
from unittest.mock import AsyncMock
from typing import Any, List

from checkmarx_one.core.exporters.scan_exporter import CheckmarxScanExporter
from base_client import BaseCheckmarxClient


class TestCheckmarxScanExporter:
    """Test cases for CheckmarxScanExporter."""

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
    def scan_exporter(self, mock_client: AsyncMock) -> CheckmarxScanExporter:
        """Create a CheckmarxScanExporter instance for testing."""
        return CheckmarxScanExporter(mock_client)

    @pytest.fixture
    def sample_scan(self) -> dict[str, Any]:
        """Sample scan data for testing."""
        return {
            "id": "scan-123",
            "projectId": "proj-123",
            "status": "completed",
            "type": "sast",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
            "results": {"high": 5, "medium": 10, "low": 15},
        }

    @pytest.fixture
    def sample_scans_batch(self, sample_scan: dict[str, Any]) -> List[dict[str, Any]]:
        """Sample batch of scans for testing."""
        return [
            sample_scan,
            {
                "id": "scan-456",
                "projectId": "proj-123",
                "status": "running",
                "type": "sca",
                "createdAt": "2024-01-02T00:00:00Z",
                "updatedAt": "2024-01-02T00:00:00Z",
                "results": None,
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
        mock_client._send_api_request.return_value = sample_scan

        result = await scan_exporter.get_scan_by_id("scan-123")

        mock_client._send_api_request.assert_called_once_with("/scans/scan-123")
        assert result == sample_scan

    @pytest.mark.asyncio
    async def test_get_scan_by_id_with_different_ids(
        self, scan_exporter: CheckmarxScanExporter, mock_client: AsyncMock
    ) -> None:
        """Test scan retrieval with different scan IDs."""
        scan_ids = ["scan-123", "scan-456", "scan-789"]

        for scan_id in scan_ids:
            mock_client._send_api_request.return_value = {"id": scan_id}
            result = await scan_exporter.get_scan_by_id(scan_id)

            mock_client._send_api_request.assert_called_with(f"/scans/{scan_id}")
            assert result["id"] == scan_id

    @pytest.mark.asyncio
    async def test_get_scans_without_parameters(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
        sample_scans_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scans without any parameters."""

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scans_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_exporter.get_scans():
            results.append(batch)

        assert len(results) == 1
        assert results[0] == sample_scans_batch

    @pytest.mark.asyncio
    async def test_get_scans_with_project_ids(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
        sample_scans_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scans with project IDs filter."""
        project_ids = ["proj-123", "proj-456"]

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scans_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_exporter.get_scans(project_ids=project_ids):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_scans_with_single_project_id(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
        sample_scans_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scans with a single project ID."""
        project_ids = ["proj-123"]

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scans_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_exporter.get_scans(project_ids=project_ids):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_scans_with_limit(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
        sample_scans_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scans with limit parameter."""

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scans_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_exporter.get_scans(limit=50):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_scans_with_offset(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
        sample_scans_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scans with offset parameter."""

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scans_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_exporter.get_scans(offset=100):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_scans_with_all_parameters(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
        sample_scans_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scans with all parameters."""
        project_ids = ["proj-123", "proj-456"]

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scans_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_exporter.get_scans(
            project_ids=project_ids, limit=25, offset=50
        ):
            results.append(batch)

        assert len(results) == 1

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

        async def mock_paginated_resources(*args, **kwargs):
            yield batch1
            yield batch2

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_exporter.get_scans():
            results.append(batch)

        assert len(results) == 2
        assert results[0] == batch1
        assert results[1] == batch2

    @pytest.mark.asyncio
    async def test_get_scans_empty_result(
        self, scan_exporter: CheckmarxScanExporter, mock_client: AsyncMock
    ) -> None:
        """Test getting scans with empty result."""

        async def mock_paginated_resources(*args, **kwargs):
            # Yield nothing - empty result
            if False:  # This ensures it's an async generator
                yield []

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_exporter.get_scans():
            results.append(batch)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_scan_by_id_exception_handling(
        self, scan_exporter: CheckmarxScanExporter, mock_client: AsyncMock
    ) -> None:
        """Test exception handling in get_scan_by_id."""
        mock_client._send_api_request.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            await scan_exporter.get_scan_by_id("scan-123")

    @pytest.mark.asyncio
    async def test_get_scans_exception_handling(
        self, scan_exporter: CheckmarxScanExporter, mock_client: AsyncMock
    ) -> None:
        """Test exception handling in get_scans."""

        async def mock_paginated_resources(*args, **kwargs):
            if True:  # This ensures it's an async generator
                raise Exception("Pagination Error")
            yield []

        mock_client._get_paginated_resources = mock_paginated_resources

        with pytest.raises(Exception, match="Pagination Error"):
            async for batch in scan_exporter.get_scans():
                pass

    def test_scan_exporter_inheritance(
        self, scan_exporter: CheckmarxScanExporter
    ) -> None:
        """Test that CheckmarxScanExporter properly inherits from AbstractCheckmarxExporter."""
        from checkmarx_one.core.exporters.abstract_exporter import (
            AbstractCheckmarxExporter,
        )

        assert isinstance(scan_exporter, AbstractCheckmarxExporter)

    def test_scan_exporter_docstring(self) -> None:
        """Test that CheckmarxScanExporter has proper documentation."""
        assert CheckmarxScanExporter.__doc__ is not None
        assert "Exporter for Checkmarx One scans" in CheckmarxScanExporter.__doc__

    def test_get_scan_by_id_docstring(self) -> None:
        """Test that get_scan_by_id method has proper documentation."""
        assert CheckmarxScanExporter.get_scan_by_id.__doc__ is not None
        assert (
            "Get a specific scan by ID" in CheckmarxScanExporter.get_scan_by_id.__doc__
        )

    def test_get_scans_docstring(self) -> None:
        """Test that get_scans method has proper documentation."""
        assert CheckmarxScanExporter.get_scans.__doc__ is not None
        assert "Get scans from Checkmarx One" in CheckmarxScanExporter.get_scans.__doc__

    @pytest.mark.asyncio
    async def test_get_scans_with_none_project_ids(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
        sample_scans_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scans with None project_ids parameter."""

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scans_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_exporter.get_scans(project_ids=None):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_scans_with_empty_project_ids(
        self,
        scan_exporter: CheckmarxScanExporter,
        mock_client: AsyncMock,
        sample_scans_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scans with empty project_ids list."""

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scans_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_exporter.get_scans(project_ids=[]):
            results.append(batch)

        assert len(results) == 1
