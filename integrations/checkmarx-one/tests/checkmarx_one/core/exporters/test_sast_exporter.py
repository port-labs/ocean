import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, AsyncIterator, List

from checkmarx_one.core.options import SingleSastOptions, ListSastOptions
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter


# Mock port_ocean imports before importing the module under test
with patch.dict(
    "sys.modules",
    {
        "port_ocean.core.ocean_types": MagicMock(),
        "port_ocean.core.integrations.base": MagicMock(),
        "port_ocean.utils.cache": MagicMock(),
    },
):
    from checkmarx_one.core.exporters.sast_exporter import CheckmarxSastExporter
    from checkmarx_one.clients.client import CheckmarxOneClient


class TestCheckmarxSastExporter:
    """Test cases for CheckmarxSastExporter."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock client for testing."""
        mock_client = MagicMock(spec=CheckmarxOneClient)
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
    def exporter(self, mock_client: MagicMock) -> CheckmarxSastExporter:
        """Create a CheckmarxSastExporter instance for testing."""
        return CheckmarxSastExporter(mock_client)

    def test_init(
        self, exporter: CheckmarxSastExporter, mock_client: MagicMock
    ) -> None:
        """Test exporter initialization."""
        assert exporter.client == mock_client

    def test_build_params_minimal(self, exporter: CheckmarxSastExporter) -> None:
        """Test building params with minimal options."""
        options: ListSastOptions = {"scan_id": "scan-123"}
        
        params = exporter._build_params(options)
        
        assert params == {
            "scan-id": "scan-123",
            "visible-columns": [
                "scan-id",
                "result-hash",
                "result-id",
                "path-system-id",
                "query-ids",
                "query-name",
                "language",
                "group",
                "cwe-id",
                "severity",
                "similarity-id",
                "confidence-level",
                "compliance",
                "first-time-scan-id",
                "first-found-at",
                "status",
                "state",
                "nodes",
            ]
        }

    @pytest.mark.asyncio
    async def test_get_resource_success(
        self, exporter: CheckmarxSastExporter, mock_client: MagicMock
    ) -> None:
        """Test getting a single SAST result by result ID."""
        scan_id = "scan-123"
        result_id = "result-456"
        options: SingleSastOptions = {"scan_id": scan_id, "result_id": result_id}
        expected_response = {
            "results": [
                {
                    "result-id": result_id,
                    "query-name": "Test Vulnerability",
                    "severity": "HIGH",
                }
            ]
        }

        mock_client.send_api_request = AsyncMock(return_value=expected_response)

        result = await exporter.get_resource(options)

        assert result == expected_response["results"][0]
        mock_client.send_api_request.assert_called_once_with(
            "/sast-results/",
            params={
                "scan-id": scan_id,
                "result-id": result_id,
                "limit": 1,
            },
        )

    @pytest.mark.asyncio
    async def test_get_resource_empty_results(
        self, exporter: CheckmarxSastExporter, mock_client: MagicMock
    ) -> None:
        """Test getting a single SAST result when no results are found."""
        scan_id = "scan-123"
        result_id = "result-456"
        options: SingleSastOptions = {"scan_id": scan_id, "result_id": result_id}
        expected_response = {"results": []}

        mock_client.send_api_request = AsyncMock(return_value=expected_response)

        result = await exporter.get_resource(options)

        assert result == {}
        mock_client.send_api_request.assert_called_once_with(
            "/sast-results/",
            params={
                "scan-id": scan_id,
                "result-id": result_id,
                "limit": 1,
            },
        )

    @pytest.mark.asyncio
    async def test_get_resource_direct_response(
        self, exporter: CheckmarxSastExporter, mock_client: MagicMock
    ) -> None:
        """Test getting a single SAST result when response is not a dict with results."""
        scan_id = "scan-123"
        result_id = "result-456"
        options: SingleSastOptions = {"scan_id": scan_id, "result_id": result_id}
        expected_response = {"result-id": result_id, "query-name": "Test Vulnerability"}

        # Create a fresh mock for this test
        fresh_mock = AsyncMock(return_value=expected_response)
        mock_client.send_api_request = fresh_mock

        result = await exporter.get_resource(options)

        # When response is not a dict with 'results' key, it should return the response as-is
        assert result == expected_response
        fresh_mock.assert_called_once_with(
            "/sast-results/",
            params={
                "scan-id": scan_id,
                "result-id": result_id,
                "limit": 1,
            },
        )

    @pytest.mark.asyncio
    async def test_get_paginated_resources_single_batch(
        self, exporter: CheckmarxSastExporter, mock_client: MagicMock
    ) -> None:
        """Test getting paginated SAST results with single batch."""
        scan_id = "scan-123"
        options: ListSastOptions = {"scan_id": scan_id}
        mock_results = [
            {"result-id": "1", "query-name": "Vulnerability 1"},
            {"result-id": "2", "query-name": "Vulnerability 2"},
        ]

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield mock_results

        mock_client.send_paginated_request = mock_paginated_resources

        results = []
        async for batch in exporter.get_paginated_resources(options):
            results.append(batch)

        assert len(results) == 1
        assert len(results[0]) == 2
        assert results[0][0]["result-id"] == "1"
        assert results[0][0]["query-name"] == "Vulnerability 1"
        assert results[0][1]["result-id"] == "2"
        assert results[0][1]["query-name"] == "Vulnerability 2"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_multiple_batches(
        self, exporter: CheckmarxSastExporter, mock_client: MagicMock
    ) -> None:
        """Test getting paginated SAST results with multiple batches."""
        scan_id = "scan-123"
        options: ListSastOptions = {"scan_id": scan_id}
        batch1 = [{"result-id": "1", "query-name": "Vulnerability 1"}]
        batch2 = [{"result-id": "2", "query-name": "Vulnerability 2"}]

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield batch1
            yield batch2

        mock_client.send_paginated_request = mock_paginated_resources

        results = []
        async for batch in exporter.get_paginated_resources(options):
            results.append(batch)

        assert len(results) == 2
        assert len(results[0]) == 1
        assert len(results[1]) == 1
        assert results[0][0]["result-id"] == "1"
        assert results[0][0]["query-name"] == "Vulnerability 1"
        assert results[1][0]["result-id"] == "2"
        assert results[1][0]["query-name"] == "Vulnerability 2"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_correct_endpoint_and_params(
        self, exporter: CheckmarxSastExporter, mock_client: MagicMock
    ) -> None:
        """Test that paginated request uses correct endpoint and params."""
        scan_id = "scan-789"
        options: ListSastOptions = {"scan_id": scan_id}
        mock_results = [{"result-id": "1", "query-name": "Test Vulnerability"}]

        call_args: dict[str, Any] = {}

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            call_args["endpoint"] = endpoint
            call_args["object_key"] = object_key
            call_args["params"] = params
            yield mock_results

        mock_client.send_paginated_request = mock_paginated_resources

        results = []
        async for batch in exporter.get_paginated_resources(options):
            results.append(batch)

        assert call_args["endpoint"] == "/sast-results/"
        assert call_args["object_key"] == "results"
        assert call_args["params"] == {
            "scan-id": scan_id,
            "visible-columns": [
                "scan-id",
                "result-hash",
                "result-id",
                "path-system-id",
                "query-ids",
                "query-name",
                "language",
                "group",
                "cwe-id",
                "severity",
                "similarity-id",
                "confidence-level",
                "compliance",
                "first-time-scan-id",
                "first-found-at",
                "status",
                "state",
                "nodes",
            ]
        }

    @pytest.mark.asyncio
    async def test_get_paginated_resources_empty_batch(
        self, exporter: CheckmarxSastExporter, mock_client: MagicMock
    ) -> None:
        """Test getting paginated SAST results with empty batch."""
        scan_id = "scan-123"
        options: ListSastOptions = {"scan_id": scan_id}
        mock_results: List[dict[str, Any]] = []

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield mock_results

        mock_client.send_paginated_request = mock_paginated_resources

        results = []
        async for batch in exporter.get_paginated_resources(options):
            results.append(batch)

        assert len(results) == 1
        assert len(results[0]) == 0

    @pytest.mark.asyncio
    async def test_get_paginated_resources_no_batches(
        self, exporter: CheckmarxSastExporter, mock_client: MagicMock
    ) -> None:
        """Test getting paginated SAST results with no batches."""
        scan_id = "scan-123"
        options: ListSastOptions = {"scan_id": scan_id}

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            # No yields - empty generator
            if False:  # ensure async generator type
                yield []

        mock_client.send_paginated_request = mock_paginated_resources

        results = []
        async for batch in exporter.get_paginated_resources(options):
            results.append(batch)

        assert len(results) == 0

    def test_build_params_with_different_scan_id(
        self, exporter: CheckmarxSastExporter
    ) -> None:
        """Test building params with different scan ID."""
        options: ListSastOptions = {"scan_id": "different-scan-456"}
        
        params = exporter._build_params(options)
        
        assert params["scan-id"] == "different-scan-456"
        assert "visible-columns" in params
        assert len(params["visible-columns"]) == 18  # All expected columns (18, not 19)

    def test_visible_columns_includes_scan_id(self, exporter: CheckmarxSastExporter) -> None:
        """Test that visible columns always includes scan-id."""
        options: ListSastOptions = {"scan_id": "scan-123"}
        
        params = exporter._build_params(options)
        
        assert "scan-id" in params["visible-columns"]
        assert params["visible-columns"][0] == "scan-id"

    def test_visible_columns_contains_all_expected_fields(
        self, exporter: CheckmarxSastExporter
    ) -> None:
        """Test that visible columns contains all expected SAST result fields."""
        options: ListSastOptions = {"scan_id": "scan-123"}
        
        params = exporter._build_params(options)
        visible_columns = params["visible-columns"]
        
        expected_fields = [
            "scan-id",
            "result-hash",
            "result-id",
            "path-system-id",
            "query-ids",
            "query-name",
            "language",
            "group",
            "cwe-id",
            "severity",
            "similarity-id",
            "confidence-level",
            "compliance",
            "first-time-scan-id",
            "first-found-at",
            "status",
            "state",
            "nodes",
        ]
        
        for field in expected_fields:
            assert field in visible_columns, f"Field {field} not found in visible columns"
        
        assert len(visible_columns) == len(expected_fields) 
