import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, AsyncIterator, List


# Mock port_ocean imports before importing the module under test
with patch.dict(
    "sys.modules",
    {
        "port_ocean.core.ocean_types": MagicMock(),
        "port_ocean.utils.cache": MagicMock(),
    },
):
    from checkmarx_one.core.exporters.kics_exporter import CheckmarxKicsExporter
from checkmarx_one.core.options import ListKicsOptions


class TestCheckmarxKicsExporter:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        mock_client = AsyncMock()
        mock_client.send_paginated_request = AsyncMock()
        return mock_client

    @pytest.fixture
    def exporter(self, mock_client: AsyncMock) -> CheckmarxKicsExporter:
        return CheckmarxKicsExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_paginated_resources_basic(
        self, exporter: CheckmarxKicsExporter, mock_client: AsyncMock
    ) -> None:
        async def gen(*args: Any, **kwargs: Any) -> AsyncIterator[List[dict[str, Any]]]:
            yield [{"ID": "a"}]
            yield [{"ID": "b"}]

        mock_client.send_paginated_request = gen

        options = ListKicsOptions(scan_id="scan-1")

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(options):
            batches.append(batch)

        assert len(batches) == 2
        assert batches[0][0]["ID"] == "a"
        assert batches[0][0]["__scan_id"] == "scan-1"
        assert batches[1][0]["ID"] == "b"
        assert batches[1][0]["__scan_id"] == "scan-1"

    def test_get_resource(self, exporter: CheckmarxKicsExporter) -> None:
        """Test that get_resource raises NotImplementedError."""
        with pytest.raises(
            NotImplementedError,
            match="Single KICS result fetch is not supported by the API.",
        ):
            exporter.get_resource({})

    @pytest.mark.asyncio
    async def test_build_params(self, exporter: CheckmarxKicsExporter) -> None:
        # Test basic scan-id only
        options = ListKicsOptions(scan_id="scan-2")
        params = exporter._build_params(options)
        assert params == {"scan-id": "scan-2"}

        # Test with filters
        options_with_filters = ListKicsOptions(
            scan_id="scan-3", severity=["HIGH", "CRITICAL"], status=["NEW", "RECURRENT"]
        )
        params_with_filters = exporter._build_params(options_with_filters)
        assert params_with_filters == {
            "scan-id": "scan-3",
            "severity": ["HIGH", "CRITICAL"],
            "status": ["NEW", "RECURRENT"],
        }
