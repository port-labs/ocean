import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any, AsyncIterator, Dict, List

from checkmarx_one.core.exporters.scan_result_exporter import (
    CheckmarxScanResultExporter,
)
from checkmarx_one.core.options import ListScanResultOptions


@pytest.fixture
def mock_client() -> MagicMock:
    """Fixture for a mocked client with async request methods."""
    client = MagicMock()
    client.send_api_request = AsyncMock()
    # Don't use AsyncMock for these since they return async generators, not coroutines
    client.send_paginated_request = MagicMock()
    client.send_paginated_request_page_index = MagicMock()
    return client


@pytest.fixture
def exporter(mock_client: MagicMock) -> CheckmarxScanResultExporter:
    """Fixture for exporter with mocked client."""
    exporter = CheckmarxScanResultExporter(mock_client)
    return exporter


def test_enrich_scan_result(exporter: CheckmarxScanResultExporter) -> None:
    scan_result: Dict[str, Any] = {"foo": "bar"}
    enriched: Dict[str, Any] = exporter._enrich_scan_result(
        scan_result, "scan-123", "proj_456"
    )

    assert enriched["foo"] == "bar"
    assert enriched["__scan_id"] == "scan-123"
    assert "__project_id" in enriched
    # Ensure it mutates the original dict
    assert scan_result["__scan_id"] == "scan-123"
    assert scan_result["__project_id"] == "proj_456"


def test_enrich_scan_result_and_project_id(
    exporter: CheckmarxScanResultExporter,
) -> None:
    scan_result: Dict[str, Any] = {"foo": "bar"}
    enriched: Dict[str, Any] = exporter._enrich_scan_result(
        scan_result, "scan-123", project_id="project-456"
    )

    assert enriched["foo"] == "bar"
    assert enriched["__scan_id"] == "scan-123"
    assert enriched["__project_id"] == "project-456"
    # Ensure it mutates the original dict
    assert scan_result["__project_id"] == "project-456"


@pytest.mark.asyncio
async def test__get_paginated_scan_results(
    exporter: CheckmarxScanResultExporter, mock_client: MagicMock
) -> None:
    mock_client.send_paginated_request_page_index.return_value = _async_gen(
        [[{"id": "1"}], [{"id": "2"}]]
    )

    params: Dict[str, Any] = {"scan-id": "scan-123"}
    results: List[Dict[str, Any]] = []
    async for batch in exporter._get_paginated_scan_results(params):
        results.extend(batch)

    assert results == [{"id": "1"}, {"id": "2"}]
    mock_client.send_paginated_request_page_index.assert_called_once_with(
        "/results", "results", {"scan-id": "scan-123"}
    )


@pytest.mark.asyncio
async def test_get_paginated_resources_filters_and_enriches(
    exporter: CheckmarxScanResultExporter, mock_client: MagicMock
) -> None:
    mock_client.send_paginated_request_page_index.return_value = _async_gen(
        [
            [{"id": "1", "type": "sast"}, {"id": "2", "type": "sca"}],
            [{"id": "3", "type": "sast"}],
        ]
    )

    options: ListScanResultOptions = {
        "scan_id": "scan-123",
        "type": "sast",
        "project_id": "proj_456",
        "branch": "",
    }
    batches: List[Dict[str, Any]] = []
    async for batch in exporter.get_paginated_resources(options):
        batches.extend(batch)

    assert batches == [
        {
            "id": "1",
            "type": "sast",
            "__scan_id": "scan-123",
            "__project_id": "proj_456",
            "__branch": "",
        },
        {
            "id": "3",
            "type": "sast",
            "__scan_id": "scan-123",
            "__project_id": "proj_456",
            "__branch": "",
        },
    ]


@pytest.mark.asyncio
async def test_get_paginated_resources_enriches_with_project_id(
    exporter: CheckmarxScanResultExporter, mock_client: MagicMock
) -> None:
    mock_client.send_paginated_request_page_index.return_value = _async_gen(
        [
            [{"id": "1", "type": "sca"}, {"id": "2", "type": "containers"}],
        ]
    )

    options: ListScanResultOptions = {
        "scan_id": "scan-123",
        "project_id": "project-456",
        "type": "sca",
        "branch": "",
    }
    batches: List[Dict[str, Any]] = []
    async for batch in exporter.get_paginated_resources(options):
        batches.extend(batch)

    assert batches == [
        {
            "id": "1",
            "type": "sca",
            "__scan_id": "scan-123",
            "__project_id": "project-456",
            "__branch": "",
        },
    ]


def test_get_params_with_all_options(exporter: CheckmarxScanResultExporter) -> None:
    options: ListScanResultOptions = {
        "scan_id": "scan-123",
        "project_id": "proj_456",
        "type": "sast",
        "branch": "",
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


@pytest.mark.asyncio
async def test_get_paginated_resources_returns_all_pages_beyond_page_size(
    exporter: CheckmarxScanResultExporter, mock_client: MagicMock
) -> None:
    """Regression: SCA/containers results must not be capped at PAGE_SIZE=100.

    The /api/results/ endpoint documents `offset` as the *number of pages to
    skip*, not the number of items.  The old code used send_paginated_request
    which incremented offset by 100 on each iteration, causing the second
    request to jump to item 10 000 and return empty results, silently capping
    every scan at 100 vulnerabilities.  This test verifies that all pages are
    consumed when a scan has more than PAGE_SIZE results.
    """
    page1 = [{"id": str(i), "type": "sca"} for i in range(100)]
    page2 = [{"id": str(i), "type": "sca"} for i in range(100, 150)]

    mock_client.send_paginated_request_page_index.return_value = _async_gen(
        [page1, page2]
    )

    options: ListScanResultOptions = {
        "scan_id": "scan-big",
        "type": "sca",
        "project_id": "proj-1",
        "branch": "main",
    }
    all_results: List[Dict[str, Any]] = []
    async for batch in exporter.get_paginated_resources(options):
        all_results.extend(batch)

    assert len(all_results) == 150, (
        "Expected all 150 SCA results across two pages; "
        "if only 100 are returned the page-index pagination bug has regressed."
    )
    mock_client.send_paginated_request_page_index.assert_called_once_with(
        "/results", "results", {"scan-id": "scan-big"}
    )


async def _async_gen(
    batches: List[List[Dict[str, Any]]]
) -> AsyncIterator[List[Dict[str, Any]]]:
    """Helper to convert list of lists into async generator."""
    for batch in batches:
        yield batch
