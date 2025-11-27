import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, Dict, List, AsyncGenerator


# Mock the integration module and other dependencies
with patch.dict(
    "sys.modules",
    {
        "integration": MagicMock(),
        "checkmarx_one.exporter_factory": MagicMock(),
        "checkmarx_one.core.exporters.dast_scan_result_exporter": MagicMock(),
    },
):
    from fetcher import (
        fetch_dast_scan_results,
    )


class TestFetcher:
    @pytest.fixture
    def mock_selector(self) -> MagicMock:
        """Create a mock selector with proper filter attributes."""
        mock_selector = MagicMock()
        mock_selector.filter.severity = ["critical", "high"]
        mock_selector.filter.status = ["new", "recurrent"]
        mock_selector.filter.state = ["to_verify", "confirmed"]
        mock_selector.dast_scan_filter.scan_type = "DAST"
        mock_selector.dast_scan_filter.updated_from_date = "2021-06-02T12:14:18.028555Z"
        mock_selector.dast_scan_filter.max_results = 3000
        return mock_selector

    @pytest.fixture
    def mock_dast_scan_environment(self) -> Dict[str, Any]:
        """Create a mock DAST scan environment."""
        return {
            "environmentId": "env-1",
            "name": "Test Environment",
            "status": "active",
        }

    @pytest.mark.asyncio
    async def test_fetch_dast_scan_results_single_batch(
        self, mock_selector: MagicMock
    ) -> None:
        """Test fetching DAST scan results with single batch."""
        mock_dast_scan_result_exporter = AsyncMock()

        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [{"resultId": "result-1", "severity": "critical"}]

        mock_dast_scan_result_exporter.get_paginated_resources = (
            mock_paginated_resources
        )

        results = await fetch_dast_scan_results(
            "scan-1", mock_selector, mock_dast_scan_result_exporter
        )

        assert len(results) == 1
        assert results[0]["resultId"] == "result-1"
        assert results[0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_fetch_dast_scan_results_multiple_batches(
        self, mock_selector: MagicMock
    ) -> None:
        """Test fetching DAST scan results with multiple batches."""
        mock_dast_scan_result_exporter = AsyncMock()

        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {"resultId": f"result-{i}", "severity": "critical"} for i in range(3)
            ]
            yield [{"resultId": f"result-{i}", "severity": "high"} for i in range(3, 5)]
            yield []  # Empty batch to test end condition

        mock_dast_scan_result_exporter.get_paginated_resources = (
            mock_paginated_resources
        )

        results = await fetch_dast_scan_results(
            "scan-1", mock_selector, mock_dast_scan_result_exporter
        )

        assert len(results) == 5
        for i in range(5):
            assert results[i]["resultId"] == f"result-{i}"

    @pytest.mark.asyncio
    async def test_fetch_dast_scan_results_multiple_batches_large(
        self, mock_selector: MagicMock
    ) -> None:
        """Test fetching DAST scan results with multiple batches (larger dataset)."""
        mock_dast_scan_result_exporter = AsyncMock()

        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            # First batch: 3 results
            yield [
                {"resultId": f"result-{i}", "severity": "critical"} for i in range(3)
            ]
            # Second batch: 2 results
            yield [{"resultId": f"result-{i}", "severity": "high"} for i in range(3, 5)]
            # Third batch: 1 result
            yield [
                {"resultId": f"result-{i}", "severity": "medium"} for i in range(5, 6)
            ]
            # Fourth batch: empty (should terminate)
            yield []

        mock_dast_scan_result_exporter.get_paginated_resources = (
            mock_paginated_resources
        )

        results = await fetch_dast_scan_results(
            "scan-1", mock_selector, mock_dast_scan_result_exporter
        )

        assert len(results) == 6
        for i in range(6):
            assert results[i]["resultId"] == f"result-{i}"

    @pytest.mark.asyncio
    async def test_fetch_dast_scan_results_calls_exporter_with_correct_options(
        self, mock_selector: MagicMock
    ) -> None:
        """Test that fetch_dast_scan_results calls exporter with correct options."""
        mock_dast_scan_result_exporter = AsyncMock()
        call_args: dict[str, Any] = {}

        async def mock_paginated_resources(
            options: Any,
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            call_args["options"] = options
            yield []

        mock_dast_scan_result_exporter.get_paginated_resources = (
            mock_paginated_resources
        )

        await fetch_dast_scan_results(
            "scan-1", mock_selector, mock_dast_scan_result_exporter
        )

        # Verify the exporter was called with correct options
        assert call_args["options"]["dast_scan_id"] == "scan-1"
        assert call_args["options"]["severity"] == ["critical", "high"]
        assert call_args["options"]["status"] == ["new", "recurrent"]
        assert call_args["options"]["state"] == ["to_verify", "confirmed"]
