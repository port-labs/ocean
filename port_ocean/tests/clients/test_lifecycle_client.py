from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from port_ocean.clients.lifecycle import LifecycleClient


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
def lifecycle_client(mock_auth: MagicMock, mock_post: AsyncMock, monkeypatch: pytest.MonkeyPatch) -> LifecycleClient:
    client = LifecycleClient(base_url="http://localhost:3017", auth=mock_auth)
    monkeypatch.setattr(client._client, "post", mock_post)
    return client


class TestLifecycleClientNotifyStarted:
    @pytest.mark.asyncio
    async def test_sends_correct_url_and_body(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        started_at = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)

        await lifecycle_client.notify_started(
            resync_id="r1",
            integration_id="i1",
            integration_type="github",
            started_at=started_at,
        )

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0] == "http://localhost:3017/v1/lifecycle/r1/i1"
        body = call_kwargs[1]["json"]
        assert body["status"] == "started"
        assert body["integration_type"] == "github"
        assert body["started_at"] == started_at.isoformat()
        assert "resync_id" not in body
        assert "integration_id" not in body

    @pytest.mark.asyncio
    async def test_defaults_started_at_to_now_when_not_provided(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_started(
            resync_id="r1",
            integration_id="i1",
            integration_type="github",
        )

        body = mock_post.call_args[1]["json"]
        assert "started_at" in body
        assert body["started_at"] is not None

    @pytest.mark.asyncio
    async def test_swallows_http_exception(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        mock_post.side_effect = httpx.ConnectError("refused")

        # Should not raise
        await lifecycle_client.notify_started(
            resync_id="r1",
            integration_id="i1",
            integration_type="github",
        )


class TestLifecycleClientNotifyFinished:
    @pytest.mark.asyncio
    async def test_sends_correct_url_and_body(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_finished(
            resync_id="r1",
            integration_id="i1",
            integration_type="github",
        )

        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0] == "http://localhost:3017/v1/lifecycle/r1/i1"
        body = call_kwargs[1]["json"]
        assert body == {"status": "finished", "integration_type": "github"}


class TestLifecycleClientNotifyFailed:
    @pytest.mark.asyncio
    async def test_sends_correct_url_and_minimal_body(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_failed(
            resync_id="r1",
            integration_id="i1",
            integration_type="github",
        )

        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0] == "http://localhost:3017/v1/lifecycle/r1/i1"
        body = call_kwargs[1]["json"]
        assert body == {"status": "failed", "integration_type": "github"}

    @pytest.mark.asyncio
    async def test_swallows_exception(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        mock_post.side_effect = Exception("network error")

        # Should not raise
        await lifecycle_client.notify_failed(
            resync_id="r1", integration_id="i1", integration_type="github"
        )


class TestLifecycleClientNotifyAborted:
    @pytest.mark.asyncio
    async def test_sends_correct_url_and_body(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        await lifecycle_client.notify_aborted(
            resync_id="r1",
            integration_id="i1",
            integration_type="github",
        )

        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0] == "http://localhost:3017/v1/lifecycle/r1/i1"
        body = call_kwargs[1]["json"]
        assert body == {"status": "aborted", "integration_type": "github"}

    @pytest.mark.asyncio
    async def test_logs_warning_on_error_response(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        error_response = MagicMock(spec=httpx.Response)
        error_response.is_error = True
        error_response.status_code = 500
        error_response.text = "internal error"
        mock_post.return_value = error_response

        from unittest.mock import patch
        with patch("port_ocean.clients.lifecycle.logger") as mock_logger:
            await lifecycle_client.notify_aborted(
                resync_id="r1", integration_id="i1", integration_type="github"
            )

        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "error" in warning_msg.lower()

    @pytest.mark.asyncio
    async def test_base_url_trailing_slash_is_stripped(
        self, mock_auth: MagicMock, monkeypatch: pytest.MonkeyPatch, mock_post: AsyncMock
    ) -> None:
        client = LifecycleClient(base_url="http://localhost:3017/", auth=mock_auth)
        monkeypatch.setattr(client._client, "post", mock_post)

        await client.notify_aborted(
            resync_id="r1", integration_id="i1", integration_type="github"
        )

        url = mock_post.call_args[0][0]
        assert url == "http://localhost:3017/v1/lifecycle/r1/i1"

    @pytest.mark.asyncio
    async def test_long_response_body_is_truncated_in_log(
        self, lifecycle_client: LifecycleClient, mock_post: AsyncMock
    ) -> None:
        long_body = "x" * 1000
        error_response = MagicMock(spec=httpx.Response)
        error_response.is_error = True
        error_response.status_code = 500
        error_response.text = long_body
        mock_post.return_value = error_response

        from unittest.mock import patch
        with patch("port_ocean.clients.lifecycle.logger") as mock_logger:
            await lifecycle_client.notify_aborted(
                resync_id="r1", integration_id="i1", integration_type="github"
            )

        logged_body = mock_logger.warning.call_args[1]["response_body"]
        assert len(logged_body) <= 257  # 256 chars + ellipsis character
        assert logged_body.endswith("…")
