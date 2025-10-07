import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, AsyncIterator, List
import types

from checkmarx_one.core.options import ListDastScanResultOptions

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
        "port_ocean.utils.cache": cache_module,
    },
):
    from checkmarx_one.core.exporters.dast_scan_result_exporter import (
        CheckmarxDastScanResultExporter,
    )
    from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter


class TestCheckmarxDastScanResultExporter:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        mock_client = AsyncMock()

        # Create an async generator placeholder for send_paginated_request
        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[List[dict[str, Any]]]:
            if False:  # ensure async generator type
                yield []

        mock_client.send_paginated_request = mock_paginated_resources
        return mock_client

    @pytest.fixture
    def exporter(self, mock_client: AsyncMock) -> CheckmarxDastScanResultExporter:
        return CheckmarxDastScanResultExporter(mock_client)

    @pytest.fixture
    def basic_options(self) -> ListDastScanResultOptions:
        return ListDastScanResultOptions(dast_scan_id="scan-1")

    @pytest.fixture
    def options_with_filters(self) -> ListDastScanResultOptions:
        return ListDastScanResultOptions(
            dast_scan_id="scan-1",
            severity=["CRITICAL", "HIGH"],
            status=["NEW", "RECURRENT"],
            state=["TO_VERIFY", "CONFIRMED"],
        )

    @pytest.mark.asyncio
    async def test_get_paginated_resources_basic(
        self,
        exporter: CheckmarxDastScanResultExporter,
        mock_client: AsyncMock,
        basic_options: ListDastScanResultOptions,
    ) -> None:
        """Test basic paginated resource fetching."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield [{"resultId": "result-1", "severity": "high"}]
            yield [{"resultId": "result-2", "severity": "medium"}]

        mock_client.send_paginated_request = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(basic_options):
            batches.append(batch)

        assert len(batches) == 2
        assert batches[0][0]["resultId"] == "result-1"
        assert batches[0][0]["__dast_scan_id"] == "scan-1"
        assert batches[1][0]["resultId"] == "result-2"
        assert batches[1][0]["__dast_scan_id"] == "scan-1"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_filters(
        self,
        exporter: CheckmarxDastScanResultExporter,
        mock_client: AsyncMock,
        options_with_filters: ListDastScanResultOptions,
    ) -> None:
        """Test paginated resource fetching with filters."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield [{"resultId": "result-1", "severity": "critical"}]

        mock_client.send_paginated_request = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(options_with_filters):
            batches.append(batch)

        assert len(batches) == 1
        assert batches[0][0]["resultId"] == "result-1"
        assert batches[0][0]["__dast_scan_id"] == "scan-1"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_empty_response(
        self,
        exporter: CheckmarxDastScanResultExporter,
        mock_client: AsyncMock,
        basic_options: ListDastScanResultOptions,
    ) -> None:
        """Test handling of empty response."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield []

        mock_client.send_paginated_request = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(basic_options):
            batches.append(batch)

        assert len(batches) == 1
        assert len(batches[0]) == 0

    @pytest.mark.asyncio
    async def test_get_resource_not_implemented(
        self, exporter: CheckmarxDastScanResultExporter
    ) -> None:
        """Test that get_resource raises NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            await exporter.get_resource({})

        assert "Fetching single DAST result is not supported" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_client_called_with_correct_endpoint_and_params(
        self,
        exporter: CheckmarxDastScanResultExporter,
        mock_client: AsyncMock,
        options_with_filters: ListDastScanResultOptions,
    ) -> None:
        """Test that client is called with correct endpoint and parameters."""
        call_args: dict[str, Any] = {}

        async def gen(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            call_args["endpoint"] = endpoint
            call_args["object_key"] = object_key
            call_args["params"] = params
            yield [{"resultId": "result-1"}]

        mock_client.send_paginated_request = gen

        async for _ in exporter.get_paginated_resources(options_with_filters):
            break

        expected_params = {
            "severity": ["CRITICAL", "HIGH"],
            "status": ["NEW", "RECURRENT"],
            "state": ["TO_VERIFY", "CONFIRMED"],
        }

        assert call_args["endpoint"] == "/dast/mfe-results/results/scan-1"
        assert call_args["object_key"] == "results"
        assert call_args["params"] == expected_params

    @pytest.mark.asyncio
    async def test_client_called_without_filters(
        self,
        exporter: CheckmarxDastScanResultExporter,
        mock_client: AsyncMock,
        basic_options: ListDastScanResultOptions,
    ) -> None:
        """Test that client is called without filters when not provided."""
        call_args: dict[str, Any] = {}

        async def gen(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            call_args["endpoint"] = endpoint
            call_args["object_key"] = object_key
            call_args["params"] = params
            yield [{"resultId": "result-1"}]

        mock_client.send_paginated_request = gen

        async for _ in exporter.get_paginated_resources(basic_options):
            break

        assert call_args["endpoint"] == "/dast/mfe-results/results/scan-1"
        assert call_args["object_key"] == "results"
        assert call_args["params"] == {}

    def test_build_params_with_all_filters(
        self, exporter: CheckmarxDastScanResultExporter
    ) -> None:
        """Test building parameters with all filters."""
        options = ListDastScanResultOptions(
            dast_scan_id="scan-1",
            severity=["CRITICAL", "HIGH"],
            status=["NEW"],
            state=["TO_VERIFY", "CONFIRMED"],
        )

        params = exporter._build_params(options)

        expected_params = {
            "severity": ["CRITICAL", "HIGH"],
            "status": ["NEW"],
            "state": ["TO_VERIFY", "CONFIRMED"],
        }
        assert params == expected_params

    def test_build_params_with_partial_filters(
        self, exporter: CheckmarxDastScanResultExporter
    ) -> None:
        """Test building parameters with only some filters."""
        options = ListDastScanResultOptions(
            dast_scan_id="scan-1", severity=["CRITICAL"], status=None, state=None
        )

        params = exporter._build_params(options)

        expected_params = {"severity": ["CRITICAL"]}
        assert params == expected_params

    def test_build_params_with_no_filters(
        self, exporter: CheckmarxDastScanResultExporter
    ) -> None:
        """Test building parameters with no filters."""
        options = ListDastScanResultOptions(
            dast_scan_id="scan-1", severity=None, status=None, state=None
        )

        params = exporter._build_params(options)

        assert params == {}

    @pytest.mark.asyncio
    async def test_enrich_scan_result_with_dast_scan_id(
        self, exporter: CheckmarxDastScanResultExporter
    ) -> None:
        """Test enriching scan result with DAST scan ID."""
        dast_scan_result = {"resultId": "result-1", "severity": "high"}
        dast_scan_id = "scan-1"

        result = exporter._enrich_scan_result_with_dast_scan_id(
            dast_scan_result, dast_scan_id
        )

        assert result["resultId"] == "result-1"
        assert result["severity"] == "high"
        assert result["__dast_scan_id"] == "scan-1"

    @pytest.mark.asyncio
    async def test_enrich_scan_result_preserves_existing_data(
        self, exporter: CheckmarxDastScanResultExporter
    ) -> None:
        """Test that enriching preserves existing result data."""
        dast_scan_result = {
            "resultId": "result-1",
            "severity": "high",
            "status": "new",
            "state": "to_verify",
            "createdAt": "2023-01-01T00:00:00Z",
        }
        dast_scan_id = "scan-1"

        result = exporter._enrich_scan_result_with_dast_scan_id(
            dast_scan_result, dast_scan_id
        )

        assert result["resultId"] == "result-1"
        assert result["severity"] == "high"
        assert result["status"] == "new"
        assert result["state"] == "to_verify"
        assert result["createdAt"] == "2023-01-01T00:00:00Z"
        assert result["__dast_scan_id"] == "scan-1"

    @pytest.mark.asyncio
    async def test_multiple_batches_handling(
        self,
        exporter: CheckmarxDastScanResultExporter,
        mock_client: AsyncMock,
        basic_options: ListDastScanResultOptions,
    ) -> None:
        """Test handling of multiple batches with different sizes."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield [{"resultId": f"result-{i}"} for i in range(3)]
            yield [{"resultId": f"result-{i}"} for i in range(3, 5)]
            yield []

        mock_client.send_paginated_request = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(basic_options):
            batches.append(batch)

        assert len(batches) == 3
        assert len(batches[0]) == 3
        assert len(batches[1]) == 2
        assert len(batches[2]) == 0

        # Check that all results are enriched with dast_scan_id
        for batch in batches:
            for result in batch:
                assert result["__dast_scan_id"] == "scan-1"

    @pytest.mark.asyncio
    async def test_exporter_inheritance(
        self, exporter: CheckmarxDastScanResultExporter
    ) -> None:
        """Test that exporter inherits from AbstractCheckmarxExporter."""
        assert isinstance(exporter, AbstractCheckmarxExporter)

    @pytest.mark.asyncio
    async def test_client_property(
        self, exporter: CheckmarxDastScanResultExporter, mock_client: AsyncMock
    ) -> None:
        """Test that client property is accessible."""
        assert exporter.client == mock_client
