import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, AsyncIterator, List
import types

from checkmarx_one.core.options import ListDastScanOptions

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
    from checkmarx_one.core.exporters.dast_scan_exporter import (
        CheckmarxDastScanExporter,
    )
    from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter


class TestCheckmarxDastScanExporter:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        mock_client = AsyncMock()

        # Create an async generator placeholder for send_paginated_request_offset_based
        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[List[dict[str, Any]]]:
            if False:  # ensure async generator type
                yield []

        mock_client.send_paginated_request_offset_based = mock_paginated_resources
        return mock_client

    @pytest.fixture
    def exporter(self, mock_client: AsyncMock) -> CheckmarxDastScanExporter:
        return CheckmarxDastScanExporter(mock_client)

    @pytest.fixture
    def basic_options(self) -> ListDastScanOptions:
        return ListDastScanOptions(
            environment_id="env-1",
            updated_from_date="2021-06-02T12:14:18.028555Z",
            max_results=3000,
        )

    @pytest.fixture
    def options_with_scan_type(self) -> ListDastScanOptions:
        return ListDastScanOptions(
            environment_id="env-1",
            scan_type="DAST",
            updated_from_date="2021-06-02T12:14:18.028555Z",
            max_results=1000,
        )

    @pytest.mark.asyncio
    async def test_get_paginated_resources_basic(
        self,
        exporter: CheckmarxDastScanExporter,
        mock_client: AsyncMock,
        basic_options: ListDastScanOptions,
    ) -> None:
        """Test basic paginated resource fetching."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield [
                {
                    "scanId": "scan-1",
                    "name": "Scan 1",
                    "updateTime": "2021-06-10T12:14:18.028555Z",
                }
            ]
            yield [
                {
                    "scanId": "scan-2",
                    "name": "Scan 2",
                    "updateTime": "2021-06-11T12:14:18.028555Z",
                }
            ]

        mock_client.send_paginated_request_offset_based = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(basic_options):
            batches.append(batch)

        assert len(batches) == 2
        assert batches[0][0]["scanId"] == "scan-1"
        assert batches[0][0]["__environment_id"] == "env-1"
        assert batches[1][0]["scanId"] == "scan-2"
        assert batches[1][0]["__environment_id"] == "env-1"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_scan_type(
        self,
        exporter: CheckmarxDastScanExporter,
        mock_client: AsyncMock,
        options_with_scan_type: ListDastScanOptions,
    ) -> None:
        """Test paginated resource fetching with scan_type filter."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield [
                {
                    "scanId": "scan-1",
                    "name": "Scan 1",
                    "updateTime": "2021-06-10T12:14:18.028555Z",
                }
            ]

        mock_client.send_paginated_request_offset_based = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(options_with_scan_type):
            batches.append(batch)

        assert len(batches) == 1
        assert batches[0][0]["scanId"] == "scan-1"
        assert batches[0][0]["__environment_id"] == "env-1"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_empty_response(
        self,
        exporter: CheckmarxDastScanExporter,
        mock_client: AsyncMock,
        basic_options: ListDastScanOptions,
    ) -> None:
        """Test handling of empty response."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield []

        mock_client.send_paginated_request_offset_based = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(basic_options):
            batches.append(batch)

        assert len(batches) == 0

    @pytest.mark.asyncio
    async def test_get_resource_not_implemented(
        self, exporter: CheckmarxDastScanExporter
    ) -> None:
        """Test that get_resource raises NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            await exporter.get_resource({})

        assert "Fetching single DAST scan is not supported" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_client_called_with_correct_endpoint_and_params(
        self,
        exporter: CheckmarxDastScanExporter,
        mock_client: AsyncMock,
        options_with_scan_type: ListDastScanOptions,
    ) -> None:
        """Test that client is called with correct endpoint and parameters."""
        call_args: dict[str, Any] = {}

        async def gen(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            call_args["endpoint"] = endpoint
            call_args["object_key"] = object_key
            call_args["params"] = params
            yield [{"scanId": "scan-1", "updateTime": "2021-06-10T12:14:18.028555Z"}]

        mock_client.send_paginated_request_offset_based = gen

        async for _ in exporter.get_paginated_resources(options_with_scan_type):
            break

        assert call_args["endpoint"] == "/dast/scans/scans"
        assert call_args["object_key"] == "scans"
        assert call_args["params"] == {
            "environmentId": "env-1",
            "sort": "updatetime:desc",
            "match.scantype": "DAST",
        }

    @pytest.mark.asyncio
    async def test_client_called_without_scan_type(
        self,
        exporter: CheckmarxDastScanExporter,
        mock_client: AsyncMock,
        basic_options: ListDastScanOptions,
    ) -> None:
        """Test that client is called without scan_type when not provided."""
        call_args: dict[str, Any] = {}

        async def gen(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            call_args["endpoint"] = endpoint
            call_args["object_key"] = object_key
            call_args["params"] = params
            yield [{"scanId": "scan-1", "updateTime": "2021-06-10T12:14:18.028555Z"}]

        mock_client.send_paginated_request_offset_based = gen

        async for _ in exporter.get_paginated_resources(basic_options):
            break

        assert call_args["endpoint"] == "/dast/scans/scans"
        assert call_args["object_key"] == "scans"
        assert call_args["params"] == {
            "environmentId": "env-1",
            "sort": "updatetime:desc",
        }

    @pytest.mark.asyncio
    async def test_enrich_dast_scan_with_environment_id(
        self, exporter: CheckmarxDastScanExporter
    ) -> None:
        """Test enriching DAST scan with environment ID."""
        dast_scan = {"scanId": "scan-1", "name": "Test Scan"}
        environment_id = "env-1"

        result = exporter._enrich_dast_scan_with_environment_id(
            dast_scan, environment_id
        )

        assert result["scanId"] == "scan-1"
        assert result["name"] == "Test Scan"
        assert result["__environment_id"] == "env-1"

    @pytest.mark.asyncio
    async def test_enrich_dast_scan_preserves_existing_data(
        self, exporter: CheckmarxDastScanExporter
    ) -> None:
        """Test that enriching preserves existing scan data."""
        dast_scan = {
            "scanId": "scan-1",
            "name": "Test Scan",
            "status": "completed",
            "createdAt": "2023-01-01T00:00:00Z",
        }
        environment_id = "env-1"

        result = exporter._enrich_dast_scan_with_environment_id(
            dast_scan, environment_id
        )

        assert result["scanId"] == "scan-1"
        assert result["name"] == "Test Scan"
        assert result["status"] == "completed"
        assert result["createdAt"] == "2023-01-01T00:00:00Z"
        assert result["__environment_id"] == "env-1"

    @pytest.mark.asyncio
    async def test_multiple_batches_handling(
        self,
        exporter: CheckmarxDastScanExporter,
        mock_client: AsyncMock,
        basic_options: ListDastScanOptions,
    ) -> None:
        """Test handling of multiple batches with different sizes."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield [
                {"scanId": f"scan-{i}", "updateTime": "2021-06-10T12:14:18.028555Z"}
                for i in range(3)
            ]
            yield [
                {"scanId": f"scan-{i}", "updateTime": "2021-06-11T12:14:18.028555Z"}
                for i in range(3, 5)
            ]

        mock_client.send_paginated_request_offset_based = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(basic_options):
            batches.append(batch)

        assert len(batches) == 2
        assert len(batches[0]) == 3
        assert len(batches[1]) == 2

        # Check that all scans are enriched with environment_id
        for batch in batches:
            for scan in batch:
                assert scan["__environment_id"] == "env-1"

    def test_build_params_with_scan_type(
        self, exporter: CheckmarxDastScanExporter
    ) -> None:
        """Test building parameters with scan_type."""
        options = ListDastScanOptions(
            environment_id="env-1",
            scan_type="DAST",
            updated_from_date="2021-06-02T12:14:18.028555Z",
            max_results=3000,
        )

        params = exporter._build_params(options)

        expected_params = {
            "environmentId": "env-1",
            "sort": "updatetime:desc",
            "match.scantype": "DAST",
        }
        assert params == expected_params

    def test_build_params_without_scan_type(
        self, exporter: CheckmarxDastScanExporter
    ) -> None:
        """Test building parameters without scan_type."""
        options = ListDastScanOptions(
            environment_id="env-1",
            updated_from_date="2021-06-02T12:14:18.028555Z",
            max_results=3000,
        )

        params = exporter._build_params(options)

        expected_params = {
            "environmentId": "env-1",
            "sort": "updatetime:desc",
        }
        assert params == expected_params

    @pytest.mark.asyncio
    async def test_date_filtering(
        self,
        exporter: CheckmarxDastScanExporter,
        mock_client: AsyncMock,
        basic_options: ListDastScanOptions,
    ) -> None:
        """Test that scans are filtered by updated_from_date."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            # Yield scans with different updateTime values
            yield [
                {
                    "scanId": "scan-1",
                    "updateTime": "2021-06-10T12:14:18.028555Z",
                },  # After cutoff
                {
                    "scanId": "scan-2",
                    "updateTime": "2021-06-01T12:14:18.028555Z",
                },  # Before cutoff
                {
                    "scanId": "scan-3",
                    "updateTime": "2021-06-15T12:14:18.028555Z",
                },  # After cutoff
            ]

        mock_client.send_paginated_request_offset_based = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(basic_options):
            batches.append(batch)

        # Only scans after 2021-06-02T12:14:18.028555Z should be returned
        assert len(batches) == 1
        assert len(batches[0]) == 2
        assert batches[0][0]["scanId"] == "scan-1"
        assert batches[0][1]["scanId"] == "scan-3"

    @pytest.mark.asyncio
    async def test_max_results_limit(
        self,
        exporter: CheckmarxDastScanExporter,
        mock_client: AsyncMock,
    ) -> None:
        """Test that max_results limit is enforced."""
        options = ListDastScanOptions(
            environment_id="env-1",
            updated_from_date="2021-06-02T12:14:18.028555Z",
            max_results=5,
        )

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            # Yield more scans than max_results
            yield [
                {"scanId": f"scan-{i}", "updateTime": "2021-06-10T12:14:18.028555Z"}
                for i in range(3)
            ]
            yield [
                {"scanId": f"scan-{i}", "updateTime": "2021-06-11T12:14:18.028555Z"}
                for i in range(3, 8)
            ]

        mock_client.send_paginated_request_offset_based = gen

        all_scans: list[dict[str, Any]] = []
        async for batch in exporter.get_paginated_resources(options):
            all_scans.extend(batch)

        # Should only return 5 scans (max_results)
        assert len(all_scans) == 5

    @pytest.mark.asyncio
    async def test_max_results_stops_early(
        self,
        exporter: CheckmarxDastScanExporter,
        mock_client: AsyncMock,
    ) -> None:
        """Test that pagination stops early when max_results is reached."""
        options = ListDastScanOptions(
            environment_id="env-1",
            updated_from_date="2021-06-02T12:14:18.028555Z",
            max_results=2,
        )

        batches_yielded = []

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            batch1 = [
                {"scanId": f"scan-{i}", "updateTime": "2021-06-10T12:14:18.028555Z"}
                for i in range(3)
            ]
            batches_yielded.append(1)
            yield batch1

            batch2 = [
                {"scanId": f"scan-{i}", "updateTime": "2021-06-11T12:14:18.028555Z"}
                for i in range(3, 6)
            ]
            batches_yielded.append(2)
            yield batch2

        mock_client.send_paginated_request_offset_based = gen

        all_scans: list[dict[str, Any]] = []
        async for batch in exporter.get_paginated_resources(options):
            all_scans.extend(batch)

        # Should only return 2 scans and stop early
        assert len(all_scans) == 2
        # Should have only processed the first batch
        assert len(batches_yielded) == 1

    @pytest.mark.asyncio
    async def test_exporter_inheritance(
        self, exporter: CheckmarxDastScanExporter
    ) -> None:
        """Test that exporter inherits from AbstractCheckmarxExporter."""
        assert isinstance(exporter, AbstractCheckmarxExporter)

    @pytest.mark.asyncio
    async def test_client_property(
        self, exporter: CheckmarxDastScanExporter, mock_client: AsyncMock
    ) -> None:
        """Test that client property is accessible."""
        assert exporter.client == mock_client
