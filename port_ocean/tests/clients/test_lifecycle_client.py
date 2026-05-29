from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from port_ocean.clients.dsp.lifecycle import (
    GranularityType,
    LifecycleClient,
    resolve_lifecycle_ingest_url,
)
from port_ocean.helpers.retry import RetryTransport


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[MagicMock, None, None]:
    with patch("port_ocean.helpers.async_client.ocean") as mock_ocean:
        mock_ocean.app.is_saas = MagicMock(return_value=False)
        yield mock_ocean


@pytest.fixture
def mock_auth() -> MagicMock:
    auth = MagicMock()
    auth.headers = AsyncMock(return_value={"Authorization": "Bearer test-token"})
    return auth


@pytest.fixture
def mock_post() -> AsyncMock:
    response = MagicMock(spec=httpx.Response)
    response.is_error = False
    response.text = '{"ok": true}'
    response.status_code = 200
    return AsyncMock(return_value=response)


@pytest.fixture
def lifecycle_client(
    mock_auth: MagicMock, mock_post: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> LifecycleClient:
    client = LifecycleClient(base_url="http://localhost:3017", auth=mock_auth)
    monkeypatch.setattr(client, "_raw_post", mock_post)
    return client


class TestResyncUrl:
    def test_resync_url(self) -> None:
        client = LifecycleClient(base_url="http://localhost:3017", auth=MagicMock())
        assert client._resync_url("r1") == "http://localhost:3017/v1/lifecycle/r1"

    def test_trailing_slash_stripped(self) -> None:
        client = LifecycleClient(base_url="http://localhost:3017/", auth=MagicMock())
        assert client._resync_url("r1") == "http://localhost:3017/v1/lifecycle/r1"


class TestGranularUrl:
    def test_kind(self) -> None:
        client = LifecycleClient(base_url="http://localhost:3017", auth=MagicMock())
        assert (
            client._granular_url("r1", GranularityType.KIND)
            == "http://localhost:3017/v1/lifecycle/r1/kind"
        )

    def test_batch(self) -> None:
        client = LifecycleClient(base_url="http://localhost:3017", auth=MagicMock())
        assert (
            client._granular_url("r1", GranularityType.BATCH)
            == "http://localhost:3017/v1/lifecycle/r1/batch"
        )

    def test_live_event(self) -> None:
        client = LifecycleClient(base_url="http://localhost:3017", auth=MagicMock())
        assert (
            client._granular_url("le1", GranularityType.LIVE_EVENT)
            == "http://localhost:3017/v1/lifecycle/le1/live_event"
        )

    def test_reconciliation(self) -> None:
        client = LifecycleClient(base_url="http://localhost:3017", auth=MagicMock())
        assert (
            client._granular_url("r1", GranularityType.RECONCILIATION)
            == "http://localhost:3017/v1/lifecycle/r1/reconciliation"
        )


class TestNotifyResyncStarted:
    @pytest.mark.asyncio
    async def test_sends_to_resync_url(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        started_at = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
        await lifecycle_client.notify_resync_started(
            resync_id="r1",
            integration_id="i1",
            integration_type="github",
            started_at=started_at,
        )
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:3017/v1/lifecycle/r1"

    @pytest.mark.asyncio
    async def test_body_has_integration_id_and_versions(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        started_at = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
        await lifecycle_client.notify_resync_started(
            resync_id="r1",
            integration_id="i1",
            integration_type="github",
            started_at=started_at,
        )
        body = mock_post.call_args[1]["json"]
        assert body["status"] == "started"
        assert body["integration_id"] == "i1"
        assert body["integration_type"] == "github"
        assert body["started_at"] == started_at.isoformat()
        assert "integration_version" in body
        assert "ocean_version" in body
        assert "granularity" not in body
        assert "event_id" not in body

    @pytest.mark.asyncio
    async def test_defaults_started_at(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        before = datetime.now(tz=timezone.utc)
        await lifecycle_client.notify_resync_started(
            resync_id="r1", integration_id="i1", integration_type="github"
        )
        after = datetime.now(tz=timezone.utc)

        body = mock_post.call_args[1]["json"]
        started_at = datetime.fromisoformat(body["started_at"])
        assert before <= started_at <= after

    @pytest.mark.asyncio
    async def test_swallows_exception(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        mock_post.side_effect = httpx.ConnectError("refused")
        await lifecycle_client.notify_resync_started(
            resync_id="r1", integration_id="i1", integration_type="github"
        )


class TestNotifyResyncFinished:
    @pytest.mark.asyncio
    async def test_sends_to_resync_url_with_finished_status(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_resync_finished(
            resync_id="r1", integration_id="i1", integration_type="github"
        )
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:3017/v1/lifecycle/r1"
        body = mock_post.call_args[1]["json"]
        assert body["status"] == "finished"
        assert body["integration_id"] == "i1"
        assert body["integration_type"] == "github"
        assert "integration_version" in body
        assert "ocean_version" in body


class TestNotifyResyncFailed:
    @pytest.mark.asyncio
    async def test_sends_to_resync_url_with_failed_status(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_resync_failed(
            resync_id="r1", integration_id="i1", integration_type="github"
        )
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:3017/v1/lifecycle/r1"
        body = mock_post.call_args[1]["json"]
        assert body == {"status": "failed"}

    @pytest.mark.asyncio
    async def test_swallows_exception(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        mock_post.side_effect = Exception("network error")
        await lifecycle_client.notify_resync_failed(
            resync_id="r1", integration_id="i1", integration_type="github"
        )


class TestNotifyResyncAborted:
    @pytest.mark.asyncio
    async def test_sends_to_resync_url_with_aborted_status(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_resync_aborted(
            resync_id="r1", integration_id="i1", integration_type="github"
        )
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:3017/v1/lifecycle/r1"
        body = mock_post.call_args[1]["json"]
        assert body == {"status": "aborted"}

    @pytest.mark.asyncio
    async def test_logs_warning_on_error_response(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        error_response = MagicMock(spec=httpx.Response)
        error_response.is_error = True
        error_response.status_code = 500
        error_response.text = "internal error"
        mock_post.return_value = error_response

        with patch("port_ocean.clients.dsp.lifecycle.logger") as mock_logger:
            await lifecycle_client.notify_resync_aborted(
                resync_id="r1", integration_id="i1", integration_type="github"
            )

        mock_logger.warning.assert_called_once()
        assert "error" in mock_logger.warning.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_long_response_body_is_truncated(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        error_response = MagicMock(spec=httpx.Response)
        error_response.is_error = True
        error_response.status_code = 500
        error_response.text = "x" * 1000
        mock_post.return_value = error_response

        with patch("port_ocean.clients.dsp.lifecycle.logger") as mock_logger:
            await lifecycle_client.notify_resync_aborted(
                resync_id="r1", integration_id="i1", integration_type="github"
            )

        logged_body = mock_logger.warning.call_args[1]["response_body"]
        assert len(logged_body) <= 257
        assert logged_body.endswith("…")


class TestNotifyGranularStarted:
    @pytest.mark.asyncio
    async def test_sends_to_granular_url(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        started_at = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
        await lifecycle_client.notify_started(
            event_id="r1",
            integration_id="i1",
            integration_type="github",
            granularity=GranularityType.KIND,
            started_at=started_at,
        )
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:3017/v1/lifecycle/r1/kind"
        body = mock_post.call_args[1]["json"]
        assert body["status"] == "started"
        assert body["integration_id"] == "i1"
        assert "granularity" not in body
        assert "event_id" not in body

    @pytest.mark.asyncio
    async def test_kind_identifier_included_when_provided(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_started(
            event_id="r1",
            integration_id="i1",
            integration_type="github",
            granularity=GranularityType.KIND,
            kind_identifier="pull-request-0",
        )
        body = mock_post.call_args[1]["json"]
        assert body["kind_identifier"] == "pull-request-0"

    @pytest.mark.asyncio
    async def test_kind_identifier_omitted_when_not_provided(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_started(
            event_id="r1",
            integration_id="i1",
            integration_type="github",
            granularity=GranularityType.KIND,
        )
        body = mock_post.call_args[1]["json"]
        assert "kind_identifier" not in body


class TestLifecycleClientIntegration:
    @pytest.mark.asyncio
    async def test_granular_started_at_defaults(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        before = datetime.now(tz=timezone.utc)
        await lifecycle_client.notify_started(
            event_id="e1",
            integration_id="i1",
            integration_type="github",
            granularity=GranularityType.BATCH,
        )
        after = datetime.now(tz=timezone.utc)

        body = mock_post.call_args[1]["json"]
        started_at = datetime.fromisoformat(body["started_at"])

        assert before <= started_at <= after

    @pytest.mark.asyncio
    async def test_multiple_calls_independent(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_resync_started(
            resync_id="r1", integration_id="i1", integration_type="github"
        )
        assert mock_post.call_count == 1

        await lifecycle_client.notify_resync_finished(
            resync_id="r1", integration_id="i1", integration_type="github"
        )
        assert mock_post.call_count == 2

        await lifecycle_client.notify_resync_failed(
            resync_id="r1", integration_id="i1", integration_type="github"
        )
        assert mock_post.call_count == 3


class TestNotifyGranularFinished:
    @pytest.mark.asyncio
    async def test_sends_to_granular_url(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_finished(
            event_id="e1",
            integration_type="github",
            granularity=GranularityType.KIND,
        )
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:3017/v1/lifecycle/e1/kind"

    @pytest.mark.asyncio
    async def test_body_has_versions_and_status(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_finished(
            event_id="e1",
            integration_type="github",
            granularity=GranularityType.BATCH,
        )
        body = mock_post.call_args[1]["json"]
        assert body["status"] == "finished"
        assert body["integration_type"] == "github"
        assert "integration_version" in body
        assert "ocean_version" in body

    @pytest.mark.asyncio
    async def test_kind_identifier_included_when_provided(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_finished(
            event_id="e1",
            integration_type="github",
            granularity=GranularityType.KIND,
            kind_identifier="svc-42",
        )
        body = mock_post.call_args[1]["json"]
        assert body["kind_identifier"] == "svc-42"

    @pytest.mark.asyncio
    async def test_kind_identifier_omitted_when_not_provided(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_finished(
            event_id="e1",
            integration_type="github",
            granularity=GranularityType.KIND,
        )
        body = mock_post.call_args[1]["json"]
        assert "kind_identifier" not in body

    @pytest.mark.asyncio
    async def test_swallows_exception(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        mock_post.side_effect = httpx.ConnectError("refused")
        await lifecycle_client.notify_finished(
            event_id="e1",
            integration_type="github",
            granularity=GranularityType.KIND,
        )


class TestNotifyGranularFailed:
    @pytest.mark.asyncio
    async def test_sends_to_granular_url(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_failed(
            event_id="e1",
            granularity=GranularityType.LIVE_EVENT,
        )
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:3017/v1/lifecycle/e1/live_event"

    @pytest.mark.asyncio
    async def test_body_has_versions_and_status(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_failed(
            event_id="e1",
            granularity=GranularityType.BATCH,
        )
        body = mock_post.call_args[1]["json"]
        assert body["status"] == "failed"
        assert "integration_version" in body
        assert "ocean_version" in body

    @pytest.mark.asyncio
    async def test_kind_identifier_included_when_provided(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_failed(
            event_id="e1",
            granularity=GranularityType.KIND,
            kind_identifier="svc-99",
        )
        body = mock_post.call_args[1]["json"]
        assert body["kind_identifier"] == "svc-99"

    @pytest.mark.asyncio
    async def test_kind_identifier_omitted_when_not_provided(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_failed(
            event_id="e1",
            granularity=GranularityType.KIND,
        )
        body = mock_post.call_args[1]["json"]
        assert "kind_identifier" not in body

    @pytest.mark.asyncio
    async def test_swallows_exception(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        mock_post.side_effect = httpx.ConnectError("refused")
        await lifecycle_client.notify_failed(
            event_id="e1",
            granularity=GranularityType.KIND,
        )


class TestNotifyGranularAborted:
    @pytest.mark.asyncio
    async def test_sends_to_granular_url(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_aborted(
            event_id="e1",
            granularity=GranularityType.RECONCILIATION,
        )
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:3017/v1/lifecycle/e1/reconciliation"

    @pytest.mark.asyncio
    async def test_body_has_versions_and_status(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_aborted(
            event_id="e1",
            granularity=GranularityType.BATCH,
        )
        body = mock_post.call_args[1]["json"]
        assert body["status"] == "aborted"
        assert "integration_version" in body
        assert "ocean_version" in body

    @pytest.mark.asyncio
    async def test_kind_identifier_omitted_when_not_provided(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_aborted(
            event_id="e1",
            granularity=GranularityType.KIND,
        )
        body = mock_post.call_args[1]["json"]
        assert "kind_identifier" not in body

    @pytest.mark.asyncio
    async def test_swallows_exception(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        mock_post.side_effect = httpx.ConnectError("refused")
        await lifecycle_client.notify_aborted(
            event_id="e1",
            granularity=GranularityType.KIND,
        )


class TestRetryBehavior:
    def _make_response(self, status_code: int) -> httpx.Response:
        return httpx.Response(status_code, content=b"")

    @staticmethod
    def _transport(client: LifecycleClient) -> RetryTransport:
        assert isinstance(client._transport, RetryTransport)
        return client._transport

    @staticmethod
    def _inner_transport(transport: RetryTransport) -> httpx.AsyncHTTPTransport:
        assert isinstance(transport._wrapped_transport, httpx.AsyncHTTPTransport)
        return transport._wrapped_transport

    @pytest.mark.asyncio
    async def test_post_retried_on_503(self, mock_auth: MagicMock) -> None:
        client = LifecycleClient(base_url="http://localhost:3017", auth=mock_auth)
        transport = self._transport(client)
        inner = self._inner_transport(transport)
        inner.handle_async_request = AsyncMock(  # type: ignore[method-assign]
            side_effect=[self._make_response(503), self._make_response(200)]
        )
        with (
            patch.object(transport, "_calculate_sleep", return_value=0.0),
            patch("port_ocean.helpers.retry.asyncio.sleep", new=AsyncMock()),
        ):
            await client.notify_resync_started(
                resync_id="r1", integration_id="i1", integration_type="github"
            )
        assert inner.handle_async_request.await_count == 2

    @pytest.mark.asyncio
    async def test_post_retried_on_connect_error(self, mock_auth: MagicMock) -> None:
        client = LifecycleClient(base_url="http://localhost:3017", auth=mock_auth)
        transport = self._transport(client)
        inner = self._inner_transport(transport)
        inner.handle_async_request = AsyncMock(  # type: ignore[method-assign]
            side_effect=[httpx.ConnectError("refused"), self._make_response(200)]
        )
        with (
            patch.object(transport, "_calculate_sleep", return_value=0.0),
            patch("port_ocean.helpers.retry.asyncio.sleep", new=AsyncMock()),
        ):
            await client.notify_resync_started(
                resync_id="r1", integration_id="i1", integration_type="github"
            )
        assert inner.handle_async_request.await_count == 2

    @pytest.mark.asyncio
    async def test_logs_warning_when_all_retries_exhausted(
        self, mock_auth: MagicMock
    ) -> None:
        client = LifecycleClient(base_url="http://localhost:3017", auth=mock_auth)
        transport = self._transport(client)
        inner = self._inner_transport(transport)
        max_attempts = 3
        transport._retry_config.max_attempts = max_attempts
        inner.handle_async_request = AsyncMock(  # type: ignore[method-assign]
            return_value=self._make_response(503)
        )
        with (
            patch.object(transport, "_calculate_sleep", return_value=0.0),
            patch("port_ocean.helpers.retry.asyncio.sleep", new=AsyncMock()),
            patch("port_ocean.clients.dsp.lifecycle.logger") as mock_logger,
        ):
            await client.notify_resync_started(
                resync_id="r1", integration_id="i1", integration_type="github"
            )
        assert inner.handle_async_request.await_count == max_attempts + 1
        mock_logger.warning.assert_called_once()


class TestResolveLifecycleIngestUrl:
    def test_eu_base_url(self) -> None:
        assert (
            resolve_lifecycle_ingest_url("https://api.getport.io")
            == "https://ingest.getport.io"
        )

    def test_us_base_url(self) -> None:
        assert (
            resolve_lifecycle_ingest_url("https://api.us.getport.io")
            == "https://ingest.us.getport.io"
        )

    def test_unknown_url_defaults_to_eu_with_warning(self) -> None:
        with patch("port_ocean.clients.dsp.lifecycle.logger") as mock_logger:
            result = resolve_lifecycle_ingest_url("https://api.custom.example.com")
            assert result == "https://ingest.getport.io"
            mock_logger.warning.assert_called_once()

    def test_local_api_base_url_maps_to_ingest_localhost(self) -> None:
        assert (
            resolve_lifecycle_ingest_url("http://api.localhost:9080")
            == "http://ingest.localhost:9080"
        )

    def test_resolver_wires_through_lifecycle_client(self) -> None:
        client = LifecycleClient(
            base_url=resolve_lifecycle_ingest_url("https://api.us.getport.io"),
            auth=MagicMock(),
        )
        assert (
            client._resync_url("r1") == "https://ingest.us.getport.io/v1/lifecycle/r1"
        )
        assert (
            client._granular_url("e1", GranularityType.KIND)
            == "https://ingest.us.getport.io/v1/lifecycle/e1/kind"
        )
