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
        return GitHubClient(base_url=BASE_URL, token=TOKEN, use_streaming=True)

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
        return GitHubClient(base_url=BASE_URL, token=TOKEN, use_streaming=True)

    @pytest.mark.asyncio
    async def test_routes_to_streaming_path_when_use_streaming_is_true(
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
            with patch.object(
                streaming_github_client,
                "_fetch_report_from_signed_url",
            ) as mock_non_streaming_fetch:
                batches: list[list[dict[str, Any]]] = []
                async for batch in streaming_github_client._download_and_yield_reports(
                    ["https://signed-url-1"]
                ):
                    batches.append(batch)

        mock_non_streaming_fetch.assert_not_called()
        assert len(batches) == 1
        assert batches[0] == records

    @pytest.mark.asyncio
    async def test_processes_multiple_signed_urls_sequentially_when_streaming(
        self, streaming_github_client: GitHubClient
    ) -> None:
        records_url_1 = _make_user_usage_records(50)
        records_url_2 = _make_user_usage_records(30)
        call_order: list[str] = []

        async def mock_stream_ndjson_report_in_batches(
            signed_url: str,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            call_order.append(signed_url)
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
        assert call_order == ["https://signed-url-1", "https://signed-url-2"]


class TestDownloadAndYieldReportsSafeStreamingPath:
    @pytest.fixture
    def streaming_github_client(self) -> GitHubClient:
        return GitHubClient(base_url=BASE_URL, token=TOKEN, use_streaming=True)

    @pytest.mark.asyncio
    async def test_routes_to_streaming_path_when_use_streaming_is_true(
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
            with patch.object(
                streaming_github_client,
                "_fetch_report_from_signed_url",
            ) as mock_non_streaming_fetch:
                batches: list[list[dict[str, Any]]] = []
                async for (
                    batch
                ) in streaming_github_client._download_and_yield_reports_safe(
                    ["https://signed-url-1"], context="test-org"
                ):
                    batches.append(batch)

        mock_non_streaming_fetch.assert_not_called()
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
    async def test_propagates_cancelled_error_without_swallowing_it(
        self, streaming_github_client: GitHubClient
    ) -> None:
        async def mock_stream_ndjson_report_in_batches(
            signed_url: str,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            raise asyncio.CancelledError()
            yield  # make it an async generator

        with patch.object(
            streaming_github_client,
            "_stream_ndjson_report_in_batches",
            mock_stream_ndjson_report_in_batches,
        ):
            with pytest.raises(asyncio.CancelledError):
                async for _ in streaming_github_client._download_and_yield_reports_safe(
                    ["https://signed-url-1"], context="test-org"
                ):
                    pass

    @pytest.mark.asyncio
    async def test_propagates_keyboard_interrupt_without_swallowing_it(
        self, streaming_github_client: GitHubClient
    ) -> None:
        async def mock_stream_ndjson_report_in_batches(
            signed_url: str,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            raise KeyboardInterrupt()
            yield  # make it an async generator

        with patch.object(
            streaming_github_client,
            "_stream_ndjson_report_in_batches",
            mock_stream_ndjson_report_in_batches,
        ):
            with pytest.raises(KeyboardInterrupt):
                async for _ in streaming_github_client._download_and_yield_reports_safe(
                    ["https://signed-url-1"], context="test-org"
                ):
                    pass

    @pytest.mark.asyncio
    async def test_logs_warning_for_failed_url_and_continues(
        self, streaming_github_client: GitHubClient
    ) -> None:
        async def mock_stream_ndjson_report_in_batches(
            signed_url: str,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            raise httpx.HTTPError("connection reset")
            yield  # make it an async generator

        with patch.object(
            streaming_github_client,
            "_stream_ndjson_report_in_batches",
            mock_stream_ndjson_report_in_batches,
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


class TestCreateGithubClientPassesStreamingConfig:
    @pytest.mark.asyncio
    async def test_passes_streaming_enabled_true_to_github_client(self) -> None:
        from clients import client_factory

        client_factory._github_client = None

        with patch("clients.client_factory.GitHubClient") as mock_github_client_class:
            mock_github_client_class.return_value = MagicMock()
            with patch(
                "clients.client_factory.ocean.config.streaming.enabled",
                True,
            ):
                client_factory._github_client = None
                client_factory.create_github_client()

        call_positional = mock_github_client_class.call_args.args
        assert (
            call_positional[3] is True
        )  # use_streaming is the 4th positional argument

    @pytest.mark.asyncio
    async def test_passes_streaming_enabled_false_to_github_client_by_default(
        self,
    ) -> None:
        from clients import client_factory

        client_factory._github_client = None

        with patch("clients.client_factory.GitHubClient") as mock_github_client_class:
            mock_github_client_class.return_value = MagicMock()
            with patch(
                "clients.client_factory.ocean.config.streaming.enabled",
                False,
            ):
                client_factory._github_client = None
                client_factory.create_github_client()

        call_positional = mock_github_client_class.call_args.args
        assert call_positional[3] is False
