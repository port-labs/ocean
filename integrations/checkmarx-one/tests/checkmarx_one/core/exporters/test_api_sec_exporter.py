import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, AsyncIterator, List
import types

from checkmarx_one.core.options import SingleApiSecOptions, ListApiSecOptions

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
    from checkmarx_one.core.exporters.api_sec_exporter import CheckmarxApiSecExporter
    from checkmarx_one.clients.client import CheckmarxOneClient


class TestCheckmarxApiSecExporter:
    """Test cases for CheckmarxApiSecExporter."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock client for testing."""
        mock_client = MagicMock(spec=CheckmarxOneClient)
        mock_client.send_api_request = AsyncMock()

        # Create an async generator placeholder for send_paginated_request_api_sec
        async def mock_paginated_resources_api_sec(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[List[dict[str, Any]]]:
            if False:  # ensure async generator type
                yield []

        mock_client.send_paginated_request_api_sec = mock_paginated_resources_api_sec
        return mock_client

    @pytest.fixture
    def exporter(self, mock_client: MagicMock) -> CheckmarxApiSecExporter:
        """Create a CheckmarxApiSecExporter instance for testing."""
        return CheckmarxApiSecExporter(mock_client)

    def test_init(
        self, exporter: CheckmarxApiSecExporter, mock_client: MagicMock
    ) -> None:
        """Test exporter initialization."""
        assert exporter.client == mock_client

    def test_enrich_scan_result_with_scan_id(
        self, exporter: CheckmarxApiSecExporter
    ) -> None:
        """Test enriching scan result with scan ID."""
        scan_result = {"risk_id": "123", "name": "Test Risk"}
        scan_id = "scan-456"

        enriched_result = exporter._enrich_scan_result_with_scan_id(
            scan_result, scan_id
        )

        assert enriched_result["__scan_id"] == scan_id
        assert enriched_result["risk_id"] == "123"
        assert enriched_result["name"] == "Test Risk"

    @pytest.mark.asyncio
    async def test_get_resource_success(
        self, exporter: CheckmarxApiSecExporter, mock_client: MagicMock
    ) -> None:
        """Test that get_resource raises NotImplementedError."""
        risk_id = "risk-123"
        options: SingleApiSecOptions = {"risk_id": risk_id}

        with pytest.raises(
            NotImplementedError,
            match="get_resource method is not implemented for API security exporter",
        ):
            await exporter.get_resource(options)

    @pytest.mark.asyncio
    async def test_get_paginated_resources_single_batch(
        self, exporter: CheckmarxApiSecExporter, mock_client: MagicMock
    ) -> None:
        """Test getting paginated API security risks with single batch."""
        scan_id = "scan-123"
        options: ListApiSecOptions = {"scan_id": scan_id}
        mock_results = [
            {"risk_id": "1", "name": "Risk 1"},
            {"risk_id": "2", "name": "Risk 2"},
        ]

        async def mock_paginated_resources_api_sec(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield mock_results

        mock_client.send_paginated_request_api_sec = mock_paginated_resources_api_sec

        results = []
        async for batch in exporter.get_paginated_resources(options):
            results.append(batch)

        assert len(results) == 1
        assert len(results[0]) == 2
        assert results[0][0]["__scan_id"] == scan_id
        assert results[0][0]["risk_id"] == "1"
        assert results[0][1]["__scan_id"] == scan_id
        assert results[0][1]["risk_id"] == "2"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_empty_result(
        self, exporter: CheckmarxApiSecExporter, mock_client: MagicMock
    ) -> None:
        """Test getting paginated API security risks with empty result."""
        scan_id = "scan-123"
        options: ListApiSecOptions = {"scan_id": scan_id}

        async def mock_paginated_resources_api_sec(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield []

        mock_client.send_paginated_request_api_sec = mock_paginated_resources_api_sec

        results = []
        async for batch in exporter.get_paginated_resources(options):
            results.append(batch)

        assert len(results) == 1
        assert len(results[0]) == 0
