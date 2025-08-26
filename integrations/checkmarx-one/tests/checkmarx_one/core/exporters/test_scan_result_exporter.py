import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, AsyncIterator, List
import types

from checkmarx_one.core.options import ListScanResultOptions, SingleScanResultOptions


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
    from checkmarx_one.core.exporters.scan_result_exporter import (
        CheckmarxScanResultExporter,
    )


class TestCheckmarxScanResultExporter:
    """Test cases for CheckmarxScanResultExporter."""

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
    def scan_result_exporter(
        self, mock_client: AsyncMock
    ) -> CheckmarxScanResultExporter:
        """Create a CheckmarxScanResultExporter instance for testing."""
        return CheckmarxScanResultExporter(mock_client)

    @pytest.fixture
    def sample_result(self) -> dict[str, Any]:
        """Sample scan result data for testing."""
        return {
            "id": "res-1",
            "severity": "HIGH",
            "state": "CONFIRMED",
            "status": "NEW",
            "type": "sast",
        }

    @pytest.fixture
    def sample_results_batch(
        self, sample_result: dict[str, Any]
    ) -> List[dict[str, Any]]:
        """Sample batch of scan results for testing."""
        return [
            sample_result,
            {
                "id": "res-2",
                "severity": "LOW",
                "state": "TO_VERIFY",
                "status": "RECURRENT",
                "type": "sast",
            },
        ]

    @pytest.mark.asyncio
    async def test_get_scan_result_by_id_success(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_result: dict[str, Any],
    ) -> None:
        """Test successful scan result retrieval by IDs."""
        mock_client.send_api_request.return_value = sample_result

        result = await scan_result_exporter.get_resource(
            SingleScanResultOptions(scan_id="scan-1", result_id="res-1")
        )

        mock_client.send_api_request.assert_called_once_with(
            "/results", params={"scan-id": "scan-1", "limit": 1}
        )
        assert result["id"] == "res-1"
        assert result["__scan_id"] == "scan-1"

    @pytest.mark.asyncio
    async def test_get_scan_results_without_filters(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_results_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scan results without any optional filters."""

        call_args: dict[str, Any] = {}

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            call_args["endpoint"] = endpoint
            call_args["object_key"] = object_key
            call_args["params"] = params
            yield sample_results_batch

        mock_client.send_paginated_request = mock_paginated_resources

        results: List[List[dict[str, Any]]] = []
        list_options = ListScanResultOptions(scan_id="scan-1", kind="sast")
        async for batch in scan_result_exporter.get_paginated_resources(list_options):
            results.append(batch)

        assert len(results) == 1
        assert results[0][0]["__scan_id"] == "scan-1"
        assert call_args["endpoint"] == "/results"
        assert call_args["object_key"] == "results"
        assert call_args["params"] == {"scan-id": "scan-1"}

    @pytest.mark.asyncio
    async def test_get_scan_results_with_filters(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_results_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scan results with filters applied."""

        call_args: dict[str, Any] = {}

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            call_args["endpoint"] = endpoint
            call_args["object_key"] = object_key
            call_args["params"] = params
            yield sample_results_batch

        mock_client.send_paginated_request = mock_paginated_resources

        results: List[List[dict[str, Any]]] = []
        list_options = ListScanResultOptions(
            scan_id="scan-1",
            kind="sast",
            severity=["CRITICAL", "HIGH"],
            state=["TO_VERIFY", "CONFIRMED"],
            status=["NEW", "RECURRENT"],
            exclude_result_types=["DEV_AND_TEST"],
        )
        async for batch in scan_result_exporter.get_paginated_resources(list_options):
            results.append(batch)

        assert len(results) == 1
        assert call_args["endpoint"] == "/results"
        assert call_args["object_key"] == "results"
        assert call_args["params"]["scan-id"] == "scan-1"
        assert call_args["params"]["severity"] == ["CRITICAL", "HIGH"]
        assert call_args["params"]["state"] == ["TO_VERIFY", "CONFIRMED"]
        assert call_args["params"]["status"] == ["NEW", "RECURRENT"]
        assert call_args["params"]["exclude-result-types"] == ["DEV_AND_TEST"]

    @pytest.mark.asyncio
    async def test_get_scan_results_multiple_batches(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_results_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scan results with multiple batches."""
        batch1 = sample_results_batch[:1]
        batch2 = sample_results_batch[1:]

        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield batch1
            yield batch2

        mock_client.send_paginated_request = mock_paginated_resources

        results: List[List[dict[str, Any]]] = []
        list_options = ListScanResultOptions(scan_id="scan-1", kind="sast")
        async for batch in scan_result_exporter.get_paginated_resources(list_options):
            results.append(batch)

        assert len(results) == 2
        assert results[0][0]["__scan_id"] == "scan-1"
        assert results[1][0]["__scan_id"] == "scan-1"

    @pytest.mark.asyncio
    async def test_get_scan_results_empty_result(
        self, scan_result_exporter: CheckmarxScanResultExporter, mock_client: AsyncMock
    ) -> None:
        """Test getting scan results with empty result."""

        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[List[dict[str, Any]]]:
            if False:  # ensure async generator type
                yield []

        mock_client.send_paginated_request = mock_paginated_resources

        results: List[List[dict[str, Any]]] = []
        list_options = ListScanResultOptions(scan_id="scan-1", kind="sast")
        async for batch in scan_result_exporter.get_paginated_resources(list_options):
            results.append(batch)

        assert len(results) == 0

    def test_scan_result_exporter_inheritance(
        self, scan_result_exporter: CheckmarxScanResultExporter
    ) -> None:
        """Test that CheckmarxScanResultExporter properly inherits from AbstractCheckmarxExporter."""
        assert hasattr(scan_result_exporter, "client")
        assert hasattr(scan_result_exporter, "get_resource")
        assert hasattr(scan_result_exporter, "get_paginated_resources")

    def test_scan_result_exporter_docstring(self) -> None:
        """Test that CheckmarxScanResultExporter has proper documentation."""
        assert CheckmarxScanResultExporter.__doc__ is not None
        assert (
            "Exporter for Checkmarx One scan results"
            in CheckmarxScanResultExporter.__doc__
        )

    def test_get_resource_docstring(self) -> None:
        """Test that get_resource method has proper documentation."""
        assert CheckmarxScanResultExporter.get_resource.__doc__ is not None
        assert (
            "Get a specific scan result by ID"
            in CheckmarxScanResultExporter.get_resource.__doc__
        )

    def test_get_paginated_resources_docstring(self) -> None:
        """Test that get_paginated_resources method has proper documentation."""
        assert CheckmarxScanResultExporter.get_paginated_resources.__doc__ is not None
        assert (
            "Get scan results from Checkmarx One"
            in CheckmarxScanResultExporter.get_paginated_resources.__doc__
        )
