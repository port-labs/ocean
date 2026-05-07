import pytest
import httpx
import asyncio
import json
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, patch, MagicMock

from clients.github_client import GitHubClient
from tests.test_client import _make_user_usage_records, _assert_chunked_correctly

BASE_URL = "https://api.github.com"
TOKEN = "test-token"


class TestStreamNdjsonReportInBatches:
    @pytest.fixture
    def streaming_github_client(self) -> GitHubClient:
        return GitHubClient(base_url=BASE_URL, token=TOKEN)

    def _build_mock_stream_context(self, ndjson_lines: list[str]) -> MagicMock:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        async def mock_aiter_lines() -> AsyncGenerator[str, None]:
            for line in ndjson_lines:
                yield line

        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_context = MagicMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_context.__aexit__ = AsyncMock(return_value=False)
        return mock_stream_context

    @pytest.mark.asyncio
    async def test_yields_fixed_size_batches_from_ndjson_lines(
        self, streaming_github_client: GitHubClient
    ) -> None:
        ndjson_lines = [
            json.dumps({"user_id": f"user_{i}", "completions": i}) for i in range(250)
        ]
        mock_stream_context = self._build_mock_stream_context(ndjson_lines)

        with patch.object(
            streaming_github_client._client,
            "stream",
            return_value=mock_stream_context,
        ):
            batches: list[list[dict[str, Any]]] = []
            async for batch in streaming_github_client._stream_ndjson_report_in_batches(
                "https://signed-url-1"
            ):
                batches.append(batch)

        _assert_chunked_correctly(
            batches,
            total_records=250,
            page_size=streaming_github_client.pagination_page_size_limit,
        )

    @pytest.mark.asyncio
    async def test_skips_empty_lines_without_yielding_them(
        self, streaming_github_client: GitHubClient
    ) -> None:
        ndjson_lines = [
            json.dumps({"user_id": "user_0"}),
            "",
            "   ",
            json.dumps({"user_id": "user_1"}),
            "",
        ]
        mock_stream_context = self._build_mock_stream_context(ndjson_lines)

        with patch.object(
            streaming_github_client._client,
            "stream",
            return_value=mock_stream_context,
        ):
            all_records: list[dict[str, Any]] = []
            async for batch in streaming_github_client._stream_ndjson_report_in_batches(
                "https://signed-url-1"
            ):
                all_records.extend(batch)

        assert len(all_records) == 2
        assert all_records[0] == {"user_id": "user_0"}
        assert all_records[1] == {"user_id": "user_1"}

    @pytest.mark.asyncio
    async def test_skips_malformed_json_lines_and_logs_warning(
        self, streaming_github_client: GitHubClient
    ) -> None:
        ndjson_lines = [
            json.dumps({"user_id": "user_0"}),
            "this is not valid json {{{",
            json.dumps({"user_id": "user_1"}),
        ]
        mock_stream_context = self._build_mock_stream_context(ndjson_lines)

        with patch.object(
            streaming_github_client._client,
            "stream",
            return_value=mock_stream_context,
        ):
            with patch("clients.github_client.logger") as mock_logger:
                all_records: list[dict[str, Any]] = []
                async for (
                    batch
                ) in streaming_github_client._stream_ndjson_report_in_batches(
                    "https://signed-url-1"
                ):
                    all_records.extend(batch)

        assert len(all_records) == 2
        assert all_records[0] == {"user_id": "user_0"}
        assert all_records[1] == {"user_id": "user_1"}
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "malformed NDJSON" in warning_message
        assert "https://signed-url-1" in warning_message

    @pytest.mark.asyncio
    async def test_yields_final_partial_batch_when_records_do_not_divide_evenly(
        self, streaming_github_client: GitHubClient
    ) -> None:
        total_records = 150
        ndjson_lines = [
            json.dumps({"user_id": f"user_{i}"}) for i in range(total_records)
        ]
        mock_stream_context = self._build_mock_stream_context(ndjson_lines)

        with patch.object(
            streaming_github_client._client,
            "stream",
            return_value=mock_stream_context,
        ):
            batches: list[list[dict[str, Any]]] = []
            async for batch in streaming_github_client._stream_ndjson_report_in_batches(
                "https://signed-url-1"
            ):
                batches.append(batch)

        _assert_chunked_correctly(
            batches,
            total_records=total_records,
            page_size=streaming_github_client.pagination_page_size_limit,
        )
        assert len(batches[-1]) == 50

    @pytest.mark.asyncio
    async def test_closes_response_when_http_error_raised_mid_stream(
        self, streaming_github_client: GitHubClient
    ) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        response_closed = {"closed": False}

        async def mock_aiter_lines_raises_mid_stream() -> AsyncGenerator[str, None]:
            yield json.dumps({"user_id": "user_0"})
            raise httpx.HTTPError("connection reset mid-stream")

        mock_response.aiter_lines = mock_aiter_lines_raises_mid_stream

        mock_stream_context = MagicMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_context.__aexit__ = AsyncMock(
            side_effect=lambda *_: response_closed.update({"closed": True}) or False
        )

        with patch.object(
            streaming_github_client._client,
            "stream",
            return_value=mock_stream_context,
        ):
            with pytest.raises(httpx.HTTPError):
                async for _ in streaming_github_client._stream_ndjson_report_in_batches(
                    "https://signed-url-1"
                ):
                    pass

        assert response_closed["closed"] is True

    @pytest.mark.asyncio
    async def test_all_records_present_across_batches_without_data_loss(
        self, streaming_github_client: GitHubClient
    ) -> None:
        total_records = 350
        ndjson_lines = [
            json.dumps({"user_id": f"user_{i}", "completions": i})
            for i in range(total_records)
        ]
        mock_stream_context = self._build_mock_stream_context(ndjson_lines)

        with patch.object(
            streaming_github_client._client,
            "stream",
            return_value=mock_stream_context,
        ):
            all_records: list[dict[str, Any]] = []
            async for batch in streaming_github_client._stream_ndjson_report_in_batches(
                "https://signed-url-1"
            ):
                all_records.extend(batch)

        assert len(all_records) == total_records
        assert all(r["user_id"] == f"user_{i}" for i, r in enumerate(all_records))


class TestDownloadAndYieldReportsStreamingPath:
    @pytest.fixture
    def streaming_github_client(self) -> GitHubClient:
        return GitHubClient(base_url=BASE_URL, token=TOKEN)

    @pytest.mark.asyncio
    async def test_streams_each_signed_url_and_yields_batches(
        self, streaming_github_client: GitHubClient
    ) -> None:
        records = _make_user_usage_records(50)

        async def mock_stream_ndjson_report_in_batches(
            signed_url: str,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield records

        with patch.object(
            streaming_github_client,
            "_stream_ndjson_report_in_batches",
            mock_stream_ndjson_report_in_batches,
        ):
            batches: list[list[dict[str, Any]]] = []
            async for batch in streaming_github_client._download_and_yield_reports(
                ["https://signed-url-1"]
            ):
                batches.append(batch)

        assert len(batches) == 1
        assert batches[0] == records

    @pytest.mark.asyncio
    async def test_processes_multiple_signed_urls_concurrently(
        self, streaming_github_client: GitHubClient
    ) -> None:
        records_url_1 = _make_user_usage_records(50)
        records_url_2 = _make_user_usage_records(30)

        async def mock_stream_ndjson_report_in_batches(
            signed_url: str,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            if "url-1" in signed_url:
                yield records_url_1
            else:
                yield records_url_2

        with patch.object(
            streaming_github_client,
            "_stream_ndjson_report_in_batches",
            mock_stream_ndjson_report_in_batches,
        ):
            all_records: list[dict[str, Any]] = []
            async for batch in streaming_github_client._download_and_yield_reports(
                ["https://signed-url-1", "https://signed-url-2"]
            ):
                all_records.extend(batch)

        assert len(all_records) == 80


class TestDownloadAndYieldReportsSafeStreamingPath:
    @pytest.fixture
    def streaming_github_client(self) -> GitHubClient:
        return GitHubClient(base_url=BASE_URL, token=TOKEN)

    @pytest.mark.asyncio
    async def test_streams_each_signed_url_and_yields_batches(
        self, streaming_github_client: GitHubClient
    ) -> None:
        records = _make_user_usage_records(50)

        async def mock_stream_ndjson_report_in_batches(
            signed_url: str,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield records

        with patch.object(
            streaming_github_client,
            "_stream_ndjson_report_in_batches",
            mock_stream_ndjson_report_in_batches,
        ):
            batches: list[list[dict[str, Any]]] = []
            async for batch in streaming_github_client._download_and_yield_reports_safe(
                ["https://signed-url-1"], context="test-org"
            ):
                batches.append(batch)

        assert len(batches) == 1
        assert batches[0] == records

    @pytest.mark.asyncio
    async def test_skips_failed_signed_url_and_continues_with_remaining_urls(
        self, streaming_github_client: GitHubClient
    ) -> None:
        successful_records = _make_user_usage_records(50)

        async def mock_stream_ndjson_report_in_batches(
            signed_url: str,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            if "failing" in signed_url:
                raise httpx.HTTPError("connection reset")
            yield successful_records

        with patch.object(
            streaming_github_client,
            "_stream_ndjson_report_in_batches",
            mock_stream_ndjson_report_in_batches,
        ):
            all_records: list[dict[str, Any]] = []
            async for batch in streaming_github_client._download_and_yield_reports_safe(
                [
                    "https://signed-url-1",
                    "https://failing-signed-url",
                    "https://signed-url-3",
                ],
                context="test-org",
            ):
                all_records.extend(batch)

        assert len(all_records) == 100

    @pytest.mark.asyncio
    async def test_cancelled_error_is_logged_as_warning_and_skipped(
        self, streaming_github_client: GitHubClient
    ) -> None:
        async def mock_fetch_report(signed_url: str) -> list[dict[str, Any]]:
            raise asyncio.CancelledError()

        with patch.object(
            streaming_github_client,
            "_fetch_report_from_signed_url",
            side_effect=mock_fetch_report,
        ):
            with patch("clients.github_client.logger") as mock_logger:
                async for _ in streaming_github_client._download_and_yield_reports_safe(
                    ["https://signed-url-1"], context="test-org"
                ):
                    pass

        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_logs_warning_for_failed_url_and_continues(
        self, streaming_github_client: GitHubClient
    ) -> None:
        async def mock_fetch_report(signed_url: str) -> list[dict[str, Any]]:
            raise httpx.HTTPError("connection reset")

        with patch.object(
            streaming_github_client,
            "_fetch_report_from_signed_url",
            side_effect=mock_fetch_report,
        ):
            with patch("clients.github_client.logger") as mock_logger:
                async for _ in streaming_github_client._download_and_yield_reports_safe(
                    ["https://signed-url-1"], context="test-org"
                ):
                    pass

        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "test-org" in warning_message
        assert "https://signed-url-1" in warning_message
