from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from port_ocean.clients.lifecycle import LifecycleClient


@pytest.fixture
def mock_auth() -> MagicMock:
    auth = MagicMock()
    auth.headers = AsyncMock(return_value={"Authorization": "Bearer test-token"})
    return auth


@pytest.fixture
def lifecycle_client(mock_auth: MagicMock) -> LifecycleClient:
    return LifecycleClient(base_url="http://localhost:3017", auth=mock_auth)


class TestLifecycleClientNotifyStarted:
    @pytest.mark.asyncio
    async def test_sends_correct_url_and_body(
        self, lifecycle_client: LifecycleClient
    ) -> None:
        started_at = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_error = False

        with patch("port_ocean.clients.lifecycle.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await lifecycle_client.notify_started(
                resync_id="r1",
                integration_id="i1",
                integration_type="github",
                started_at=started_at,
            )

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "http://localhost:3017/v1/lifecycle/r1/i1"
        body = call_kwargs[1]["json"]
        assert body["status"] == "started"
        assert body["integration_type"] == "github"
        assert body["started_at"] == started_at.isoformat()
        assert "resync_id" not in body
        assert "integration_id" not in body

    @pytest.mark.asyncio
    async def test_defaults_started_at_to_now_when_not_provided(
        self, lifecycle_client: LifecycleClient
    ) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_error = False

        with patch("port_ocean.clients.lifecycle.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await lifecycle_client.notify_started(
                resync_id="r1",
                integration_id="i1",
                integration_type="github",
            )

        body = mock_client.post.call_args[1]["json"]
        assert "started_at" in body
        assert body["started_at"] is not None

    @pytest.mark.asyncio
    async def test_swallows_http_exception(
        self, lifecycle_client: LifecycleClient
    ) -> None:
        with patch("port_ocean.clients.lifecycle.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client_cls.return_value = mock_client

            # Should not raise
            await lifecycle_client.notify_started(
                resync_id="r1",
                integration_id="i1",
                integration_type="github",
            )


class TestLifecycleClientNotifyFinished:
    @pytest.mark.asyncio
    async def test_sends_correct_url_and_body(
        self, lifecycle_client: LifecycleClient
    ) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_error = False

        with patch("port_ocean.clients.lifecycle.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await lifecycle_client.notify_finished(
                resync_id="r1",
                integration_id="i1",
                integration_type="github",
            )

        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "http://localhost:3017/v1/lifecycle/r1/i1"
        body = call_kwargs[1]["json"]
        assert body == {"status": "finished", "integration_type": "github"}


class TestLifecycleClientNotifyFailed:
    @pytest.mark.asyncio
    async def test_sends_correct_url_and_minimal_body(
        self, lifecycle_client: LifecycleClient
    ) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_error = False

        with patch("port_ocean.clients.lifecycle.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await lifecycle_client.notify_failed(
                resync_id="r1",
                integration_id="i1",
                integration_type="github",
            )

        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "http://localhost:3017/v1/lifecycle/r1/i1"
        body = call_kwargs[1]["json"]
        assert body == {"status": "failed", "integration_type": "github"}

    @pytest.mark.asyncio
    async def test_swallows_exception(self, lifecycle_client: LifecycleClient) -> None:
        with patch("port_ocean.clients.lifecycle.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=Exception("network error"))
            mock_client_cls.return_value = mock_client

            # Should not raise
            await lifecycle_client.notify_failed(
                resync_id="r1", integration_id="i1", integration_type="github"
            )


class TestLifecycleClientNotifyAborted:
    @pytest.mark.asyncio
    async def test_sends_correct_url_and_body(
        self, lifecycle_client: LifecycleClient
    ) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_error = False

        with patch("port_ocean.clients.lifecycle.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await lifecycle_client.notify_aborted(
                resync_id="r1",
                integration_id="i1",
                integration_type="github",
            )

        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "http://localhost:3017/v1/lifecycle/r1/i1"
        body = call_kwargs[1]["json"]
        assert body == {"status": "aborted", "integration_type": "github"}

    @pytest.mark.asyncio
    async def test_logs_warning_on_error_response(
        self, lifecycle_client: LifecycleClient
    ) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_error = True
        mock_response.status_code = 500
        mock_response.text = "internal error"

        with (
            patch("port_ocean.clients.lifecycle.httpx.AsyncClient") as mock_client_cls,
            patch("port_ocean.clients.lifecycle.logger") as mock_logger,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await lifecycle_client.notify_aborted(
                resync_id="r1", integration_id="i1", integration_type="github"
            )

        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "error" in warning_msg.lower()

    @pytest.mark.asyncio
    async def test_base_url_trailing_slash_is_stripped(
        self, mock_auth: MagicMock
    ) -> None:
        client = LifecycleClient(base_url="http://localhost:3017/", auth=mock_auth)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_error = False

        with patch("port_ocean.clients.lifecycle.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await client.notify_aborted(
                resync_id="r1", integration_id="i1", integration_type="github"
            )

        url = mock_client.post.call_args[0][0]
        assert url == "http://localhost:3017/v1/lifecycle/r1/i1"
