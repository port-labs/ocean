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

    def test_enrich_dast_result_with_scan_id(
        self, exporter: CheckmarxDastExporter
    ) -> None:
        """Test that DAST results are enriched with scan_id."""
        result = {"id": "test-id", "name": "Test Finding"}
        scan_id = "scan-123"

        enriched = exporter._enrich_dast_result_with_scan_id(result, scan_id)

        assert enriched["__scan_id"] == scan_id
        assert enriched["id"] == "test-id"
        assert enriched["name"] == "Test Finding"

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
        # Should be enriched with scan_id
        expected_enriched = {**expected, "__scan_id": scan_id}
        assert result == expected_enriched
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
        # Results should be enriched with scan_id
        expected_enriched = [
            {**result, "__scan_id": scan_id} for result in mock_results
        ]
        assert batches[0] == expected_enriched

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

    @pytest.mark.asyncio
    async def test_get_paginated_resources_handles_404_gracefully(
        self, exporter: CheckmarxDastExporter, mock_client: MagicMock
    ) -> None:
        """Test that 404 errors are handled gracefully when scan has no DAST results."""
        scan_id = "scan-123"
        options: ListDastOptions = {"scan_id": scan_id}

        # Mock the client to raise a 404 error
        async def mock_paginated_resources_404(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            if False:  # This ensures it's an async generator
                yield []
            raise Exception("HTTP error 404 for GET: failed to find scanID")

        mock_client.send_paginated_request_dast = mock_paginated_resources_404

        batches: list[list[dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(options):
            batches.append(batch)

        # Should return no batches when 404 error occurs
        assert len(batches) == 0

    @pytest.mark.asyncio
    async def test_get_paginated_resources_raises_non_404_errors(
        self, exporter: CheckmarxDastExporter, mock_client: MagicMock
    ) -> None:
        """Test that non-404 errors are still raised."""
        scan_id = "scan-123"
        options: ListDastOptions = {"scan_id": scan_id}

        # Mock the client to raise a non-404 error
        async def mock_paginated_resources_500(
            endpoint: str, object_key: str, params: dict[str, Any] | None = None
        ) -> AsyncIterator[List[dict[str, Any]]]:
            if False:  # This ensures it's an async generator
                yield []
            raise Exception("HTTP error 500 for GET: Internal server error")

        mock_client.send_paginated_request_dast = mock_paginated_resources_500

        with pytest.raises(Exception, match="HTTP error 500"):
            batches: list[list[dict[str, Any]]] = []
            async for batch in exporter.get_paginated_resources(options):
                batches.append(batch)
