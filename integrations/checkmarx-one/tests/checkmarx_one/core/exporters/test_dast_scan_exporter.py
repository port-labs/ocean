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

        # Create an async generator placeholder for send_paginated_request
        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[List[dict[str, Any]]]:
            if False:  # ensure async generator type
                yield []

        mock_client.send_paginated_request = mock_paginated_resources
        return mock_client

    @pytest.fixture
    def exporter(self, mock_client: AsyncMock) -> CheckmarxDastScanExporter:
        return CheckmarxDastScanExporter(mock_client)

    @pytest.fixture
    def basic_options(self) -> ListDastScanOptions:
        return ListDastScanOptions(environment_id="env-1")

    @pytest.fixture
    def options_with_groups(self) -> ListDastScanOptions:
        return ListDastScanOptions(environment_id="env-1", groups=["group1", "group2"])

    @pytest.mark.asyncio
    async def test_get_paginated_resources_basic(
        self,
        exporter: CheckmarxDastScanExporter,
        mock_client: AsyncMock,
        basic_options: ListDastScanOptions,
    ) -> None:
        """Test basic paginated resource fetching."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield [{"scanId": "scan-1", "name": "Scan 1"}]
            yield [{"scanId": "scan-2", "name": "Scan 2"}]

        mock_client.send_paginated_request = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(basic_options):
            batches.append(batch)

        assert len(batches) == 2
        assert batches[0][0]["scanId"] == "scan-1"
        assert batches[0][0]["__environment_id"] == "env-1"
        assert batches[1][0]["scanId"] == "scan-2"
        assert batches[1][0]["__environment_id"] == "env-1"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_groups(
        self,
        exporter: CheckmarxDastScanExporter,
        mock_client: AsyncMock,
        options_with_groups: ListDastScanOptions,
    ) -> None:
        """Test paginated resource fetching with groups filter."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield [{"scanId": "scan-1", "name": "Scan 1"}]

        mock_client.send_paginated_request = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(options_with_groups):
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

        mock_client.send_paginated_request = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(basic_options):
            batches.append(batch)

        assert len(batches) == 1
        assert len(batches[0]) == 0

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
        options_with_groups: ListDastScanOptions,
    ) -> None:
        """Test that client is called with correct endpoint and parameters."""
        call_args: dict[str, Any] = {}

        async def gen(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            call_args["endpoint"] = endpoint
            call_args["object_key"] = object_key
            call_args["params"] = params
            yield [{"scanId": "scan-1"}]

        mock_client.send_paginated_request = gen

        async for _ in exporter.get_paginated_resources(options_with_groups):
            break

        assert call_args["endpoint"] == "/dast/scans/scans"
        assert call_args["object_key"] == "scans"
        assert call_args["params"] == {
            "environmentID": "env-1",
            "groups": ["group1", "group2"],
        }

    @pytest.mark.asyncio
    async def test_client_called_without_groups(
        self,
        exporter: CheckmarxDastScanExporter,
        mock_client: AsyncMock,
        basic_options: ListDastScanOptions,
    ) -> None:
        """Test that client is called without groups when not provided."""
        call_args: dict[str, Any] = {}

        async def gen(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            call_args["endpoint"] = endpoint
            call_args["object_key"] = object_key
            call_args["params"] = params
            yield [{"scanId": "scan-1"}]

        mock_client.send_paginated_request = gen

        async for _ in exporter.get_paginated_resources(basic_options):
            break

        assert call_args["endpoint"] == "/dast/scans/scans"
        assert call_args["object_key"] == "scans"
        assert call_args["params"] == {"environmentID": "env-1"}

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
            yield [{"scanId": f"scan-{i}"} for i in range(3)]
            yield [{"scanId": f"scan-{i}"} for i in range(3, 5)]
            yield []

        mock_client.send_paginated_request = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(basic_options):
            batches.append(batch)

        assert len(batches) == 3
        assert len(batches[0]) == 3
        assert len(batches[1]) == 2
        assert len(batches[2]) == 0

        # Check that all scans are enriched with environment_id
        for batch in batches:
            for scan in batch:
                assert scan["__environment_id"] == "env-1"

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
