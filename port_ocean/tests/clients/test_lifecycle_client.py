import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from port_ocean.clients.dsp.lifecycle import GranularityType, LifecycleClient


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
    # Mock the underlying httpx client's post method instead of OceanHttpClient.post
    # This allows the @retry_transient_network decorator to properly handle exceptions
    mock_httpx_client = MagicMock(spec=httpx.AsyncClient)
    mock_httpx_client.post = mock_post
    monkeypatch.setattr(client._client, "_client", mock_httpx_client)
    # Skip actual sleep delays during retries to speed up tests
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
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
        await lifecycle_client.notify_resync_started(
            resync_id="r1", integration_id="i1", integration_type="github"
        )
        body = mock_post.call_args[1]["json"]
        assert "started_at" in body

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

        with patch("port_ocean.clients.core_client.logger") as mock_logger:
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

        with patch("port_ocean.clients.core_client.logger") as mock_logger:
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
    async def test_reconciliation_uses_granular_url(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_started(
            event_id="r1",
            integration_id="i1",
            integration_type="github",
            granularity=GranularityType.RECONCILIATION,
        )
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:3017/v1/lifecycle/r1/reconciliation"

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
    async def test_notify_finished_includes_versions(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_resync_finished(
            resync_id="r1", integration_id="i1", integration_type="github"
        )
        body = mock_post.call_args[1]["json"]
        assert "integration_version" in body
        assert "ocean_version" in body

    @pytest.mark.asyncio
    async def test_notify_failed_minimal_body(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_resync_failed(
            resync_id="r1", integration_id="i1", integration_type="github"
        )
        body = mock_post.call_args[1]["json"]
        assert body == {"status": "failed"}

    @pytest.mark.asyncio
    async def test_notify_finished_granular(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_finished(
            event_id="e1",
            integration_type="github",
            granularity=GranularityType.BATCH,
        )
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:3017/v1/lifecycle/e1/batch"
        body = mock_post.call_args[1]["json"]
        assert body["status"] == "finished"
        assert body["integration_type"] == "github"

    @pytest.mark.asyncio
    async def test_notify_failed_granular(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_failed(
            event_id="e1",
            granularity=GranularityType.LIVE_EVENT,
        )
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:3017/v1/lifecycle/e1/live_event"
        body = mock_post.call_args[1]["json"]
        assert body["status"] == "failed"

    @pytest.mark.asyncio
    async def test_notify_aborted_granular(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_aborted(
            event_id="e1",
            granularity=GranularityType.KIND,
            kind_identifier="service-123",
        )
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:3017/v1/lifecycle/e1/kind"
        body = mock_post.call_args[1]["json"]
        assert body["status"] == "aborted"
        assert body["kind_identifier"] == "service-123"

    @pytest.mark.asyncio
    async def test_base_url_normalization(self, mock_auth: MagicMock) -> None:
        # Test with trailing slash
        client = LifecycleClient(base_url="http://localhost:3017/", auth=mock_auth)
        assert client._resync_url("r1") == "http://localhost:3017/v1/lifecycle/r1"

    @pytest.mark.asyncio
    async def test_started_at_defaults_to_now(
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
