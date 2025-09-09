import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, AsyncIterator, List


# Mock port_ocean imports before importing the module under test
with patch.dict(
    "sys.modules",
    {
        "port_ocean.core.ocean_types": MagicMock(),
        "port_ocean.core.integrations.base": MagicMock(),
        "port_ocean.utils.cache": MagicMock(),
    },
):
    from checkmarx_one.core.options import ListDastOptions, SingleDastOptions
    from checkmarx_one.core.exporters.dast_exporter import CheckmarxDastExporter
    from checkmarx_one.clients.client import CheckmarxOneClient


class TestCheckmarxDastExporter:
    @pytest.fixture
    def mock_client(self) -> MagicMock:
        mock_client = MagicMock(spec=CheckmarxOneClient)
        mock_client.send_api_request = AsyncMock()

        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[List[dict[str, Any]]]:
            if False:
                yield []

        mock_client.send_paginated_request_dast = mock_paginated_resources
        return mock_client

    @pytest.fixture
    def exporter(self, mock_client: MagicMock) -> CheckmarxDastExporter:
        return CheckmarxDastExporter(mock_client)

    def test_init(
        self, exporter: CheckmarxDastExporter, mock_client: MagicMock
    ) -> None:
        assert exporter.client == mock_client

    @pytest.mark.asyncio
    async def test_get_resource_success(
        self, exporter: CheckmarxDastExporter, mock_client: MagicMock
    ) -> None:
        scan_id = "scan-123"
        result_id = "res-456"
        options: SingleDastOptions = {"scan_id": scan_id, "result_id": result_id}
        expected = {"id": result_id, "severity": "HIGH"}

        mock_client.send_api_request = AsyncMock(return_value=expected)

        result = await exporter.get_resource(options)
        assert result == expected
        mock_client.send_api_request.assert_called_once_with(
            f"/dast/mfe-results/results/info/{result_id}/{scan_id}"
        )

    @pytest.mark.asyncio
    async def test_get_paginated_resources_single_batch(
        self, exporter: CheckmarxDastExporter, mock_client: MagicMock
    ) -> None:
        scan_id = "scan-123"
        options: ListDastOptions = {"scan_id": scan_id}
        mock_results = [{"id": "1"}, {"id": "2"}]

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield mock_results

        mock_client.send_paginated_request_dast = mock_paginated_resources

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(options):
            batches.append(batch)

        assert len(batches) == 1
        assert batches[0] == mock_results

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_filter_json(
        self, exporter: CheckmarxDastExporter, mock_client: MagicMock
    ) -> None:
        scan_id = "scan-123"
        options: ListDastOptions = {"scan_id": scan_id, "filter": {"severity": "HIGH"}}
        captured_params: dict[str, Any] | None = None

        async def mock_paginated_resources(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            nonlocal captured_params
            captured_params = params or {}
            yield []

        mock_client.send_paginated_request_dast = mock_paginated_resources

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(options):
            batches.append(batch)

        assert captured_params is not None
        # filter should be encoded as JSON string
        assert isinstance(captured_params.get("filter"), str)
