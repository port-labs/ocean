import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, AsyncIterator, List
import types


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
    from checkmarx_one.core.exporters.dast_scan_environment_exporter import (
        CheckmarxDastScanEnvironmentExporter,
    )
    from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter


class TestCheckmarxDastScanEnvironmentExporter:
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
    def exporter(self, mock_client: AsyncMock) -> CheckmarxDastScanEnvironmentExporter:
        return CheckmarxDastScanEnvironmentExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_paginated_resources_basic(
        self, exporter: CheckmarxDastScanEnvironmentExporter, mock_client: AsyncMock
    ) -> None:
        """Test basic paginated resource fetching."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield [{"environmentId": "env-1", "name": "Environment 1"}]
            yield [{"environmentId": "env-2", "name": "Environment 2"}]

        mock_client.send_paginated_request = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources():
            batches.append(batch)

        assert len(batches) == 2
        assert batches[0][0]["environmentId"] == "env-1"
        assert batches[0][0]["name"] == "Environment 1"
        assert batches[1][0]["environmentId"] == "env-2"
        assert batches[1][0]["name"] == "Environment 2"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_empty_response(
        self, exporter: CheckmarxDastScanEnvironmentExporter, mock_client: AsyncMock
    ) -> None:
        """Test handling of empty response."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield []

        mock_client.send_paginated_request = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources():
            batches.append(batch)

        assert len(batches) == 1
        assert len(batches[0]) == 0

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_options(
        self, exporter: CheckmarxDastScanEnvironmentExporter, mock_client: AsyncMock
    ) -> None:
        """Test paginated resource fetching with options parameter."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield [{"environmentId": "env-1", "name": "Environment 1"}]

        mock_client.send_paginated_request = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(options=None):
            batches.append(batch)

        assert len(batches) == 1
        assert batches[0][0]["environmentId"] == "env-1"

    @pytest.mark.asyncio
    async def test_get_resource_not_implemented(
        self, exporter: CheckmarxDastScanEnvironmentExporter
    ) -> None:
        """Test that get_resource raises NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            await exporter.get_resource({})

        assert "Fetching single DAST scan environment is not supported" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_client_called_with_correct_endpoint(
        self, exporter: CheckmarxDastScanEnvironmentExporter, mock_client: AsyncMock
    ) -> None:
        """Test that client is called with correct endpoint and parameters."""
        call_args: dict[str, Any] = {}

        async def gen(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            call_args["endpoint"] = endpoint
            call_args["object_key"] = object_key
            call_args["params"] = params
            yield [{"environmentId": "env-1"}]

        mock_client.send_paginated_request = gen

        async for _ in exporter.get_paginated_resources():
            break

        assert call_args["endpoint"] == "/dast/scans/environments"
        assert call_args["object_key"] == "environments"

    @pytest.mark.asyncio
    async def test_multiple_batches_handling(
        self, exporter: CheckmarxDastScanEnvironmentExporter, mock_client: AsyncMock
    ) -> None:
        """Test handling of multiple batches with different sizes."""

        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield [{"environmentId": f"env-{i}"} for i in range(3)]
            yield [{"environmentId": f"env-{i}"} for i in range(3, 5)]
            yield []

        mock_client.send_paginated_request = gen

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources():
            batches.append(batch)

        assert len(batches) == 3
        assert len(batches[0]) == 3
        assert len(batches[1]) == 2
        assert len(batches[2]) == 0

    @pytest.mark.asyncio
    async def test_exporter_inheritance(
        self, exporter: CheckmarxDastScanEnvironmentExporter
    ) -> None:
        """Test that exporter inherits from AbstractCheckmarxExporter."""
        assert isinstance(exporter, AbstractCheckmarxExporter)

    @pytest.mark.asyncio
    async def test_client_property(
        self, exporter: CheckmarxDastScanEnvironmentExporter, mock_client: AsyncMock
    ) -> None:
        """Test that client property is accessible."""
        assert exporter.client == mock_client
