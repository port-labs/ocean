import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any, AsyncIterator, Dict, List

from checkmarx_one.core.exporters.scan_result_exporter import (
    CheckmarxScanResultExporter,
)
from checkmarx_one.core.options import SingleScanResultOptions, ListScanResultOptions


@pytest.fixture
def mock_client() -> MagicMock:
    """Fixture for a mocked client with async request methods."""
    client = MagicMock()
    client.send_api_request = AsyncMock()
    # Don't use AsyncMock for send_paginated_request since it returns an async generator, not a coroutine
    client.send_paginated_request = MagicMock()
    return client


@pytest.fixture
def exporter(mock_client: MagicMock) -> CheckmarxScanResultExporter:
    """Fixture for exporter with mocked client."""
    exporter = CheckmarxScanResultExporter(mock_client)
    return exporter


def test_enrich_scan_result_with_scan_id(exporter: CheckmarxScanResultExporter) -> None:
    scan_result: Dict[str, Any] = {"foo": "bar"}
    enriched: Dict[str, Any] = exporter._enrich_scan_result_with_scan_id(
        scan_result, "scan-123"
    )

    assert enriched["foo"] == "bar"
    assert enriched["__scan_id"] == "scan-123"
    # Ensure it mutates the original dict
    assert scan_result["__scan_id"] == "scan-123"


@pytest.mark.asyncio
async def test_get_resource(
    exporter: CheckmarxScanResultExporter, mock_client: MagicMock
) -> None:
    options: SingleScanResultOptions = {
        "scan_id": "scan-123",
        "result_id": "result-1",
        "type": "sca",
    }

    with pytest.raises(
        NotImplementedError,
        match="get_resource method is not implemented for scan result exporter",
    ):
        await exporter.get_resource(options)


@pytest.mark.asyncio
async def test__get_paginated_scan_results(
    exporter: CheckmarxScanResultExporter, mock_client: MagicMock
) -> None:
    mock_client.send_paginated_request.return_value = _async_gen(
        [[{"id": "1"}], [{"id": "2"}]]
    )

    params: Dict[str, Any] = {"scan-id": "scan-123"}
    results: List[Dict[str, Any]] = []
    async for batch in exporter._get_paginated_scan_results(params):
        results.extend(batch)

    assert results == [{"id": "1"}, {"id": "2"}]
    mock_client.send_paginated_request.assert_called_once_with(
        "/results", "results", {"scan-id": "scan-123"}
    )


@pytest.mark.asyncio
async def test_get_paginated_resources_filters_and_enriches(
    exporter: CheckmarxScanResultExporter, mock_client: MagicMock
) -> None:
    mock_client.send_paginated_request.return_value = _async_gen(
        [
            [{"id": "1", "type": "sast"}, {"id": "2", "type": "sca"}],
            [{"id": "3", "type": "sast"}],
        ]
    )

    options: ListScanResultOptions = {"scan_id": "scan-123", "type": "sast"}
    batches: List[Dict[str, Any]] = []
    async for batch in exporter.get_paginated_resources(options):
        batches.extend(batch)

    assert batches == [
        {"id": "1", "type": "sast", "__scan_id": "scan-123"},
        {"id": "3", "type": "sast", "__scan_id": "scan-123"},
    ]


def test_get_params_with_all_options(exporter: CheckmarxScanResultExporter) -> None:
    options: ListScanResultOptions = {
        "scan_id": "scan-123",
        "type": "sast",
        "severity": ["HIGH"],
        "state": ["CONFIRMED"],
        "status": ["NEW"],
        "exclude_result_types": "DEV_AND_TEST",
    }
    params: Dict[str, Any] = exporter._get_params(options)

    assert params == {
        "scan-id": "scan-123",
        "severity": "HIGH",
        "state": "CONFIRMED",
        "status": "NEW",
        "exclude-result-types": "DEV_AND_TEST",
    }


async def _async_gen(
    batches: List[List[Dict[str, Any]]]
) -> AsyncIterator[List[Dict[str, Any]]]:
    """Helper to convert list of lists into async generator."""
    for batch in batches:
        yield batch
