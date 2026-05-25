import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from port_ocean.clients.core_client import OceanHttpClient


@pytest.fixture
def mock_auth() -> MagicMock:
    auth = MagicMock()
    auth.headers = AsyncMock(return_value={"Authorization": "Bearer test-token"})
    return auth


@pytest.fixture
def core_client(
    mock_auth: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> OceanHttpClient:
    client = OceanHttpClient(auth=mock_auth, timeout=10)
    # Mock asyncio.sleep to avoid delays during tests
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    return client


class TestOceanHttpClientInitialization:
    def test_client_initializes_with_auth_and_timeout(
        self, mock_auth: MagicMock
    ) -> None:
        client = OceanHttpClient(auth=mock_auth, timeout=30)
        assert client.auth == mock_auth
        assert client._timeout == 30

    def test_httpx_client_lazy_loads(self, core_client: OceanHttpClient) -> None:
        assert core_client._client is None
        # First access triggers lazy load
        client = core_client._get_client()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)


class TestOceanHttpClientPost:
    @pytest.mark.asyncio
    async def test_post_success(
        self,
        core_client: OceanHttpClient,
        mock_auth: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_error = False
        mock_response.status_code = 200
        mock_response.text = '{"ok": true}'

        mock_httpx_client = MagicMock(spec=httpx.AsyncClient)
        mock_httpx_client.post = AsyncMock(return_value=mock_response)
        monkeypatch.setattr(core_client, "_client", mock_httpx_client)

        # Should complete without raising
        await core_client.post("http://example.com", json={"test": "data"})

        mock_httpx_client.post.assert_called_once()
        assert mock_httpx_client.post.call_args[0][0] == "http://example.com"
        assert mock_httpx_client.post.call_args[1]["json"] == {"test": "data"}
        assert mock_httpx_client.post.call_args[1]["headers"] == {
            "Authorization": "Bearer test-token"
        }

    @pytest.mark.asyncio
    async def test_post_retries_on_connect_error(
        self, core_client: OceanHttpClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_error = False
        mock_response.status_code = 200

        mock_httpx_client = MagicMock(spec=httpx.AsyncClient)
        # First two calls fail, third succeeds
        mock_httpx_client.post = AsyncMock(
            side_effect=[
                httpx.ConnectError("connection failed"),
                httpx.ConnectError("connection failed"),
                mock_response,
            ]
        )
        monkeypatch.setattr(core_client, "_client", mock_httpx_client)

        # Should succeed after retries
        await core_client.post("http://example.com", json={"test": "data"})

        assert mock_httpx_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_post_retries_on_timeout(
        self, core_client: OceanHttpClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_error = False
        mock_response.status_code = 200

        mock_httpx_client = MagicMock(spec=httpx.AsyncClient)
        mock_httpx_client.post = AsyncMock(
            side_effect=[
                httpx.TimeoutException("read timeout"),
                mock_response,
            ]
        )
        monkeypatch.setattr(core_client, "_client", mock_httpx_client)

        await core_client.post("http://example.com", json={"test": "data"})

        assert mock_httpx_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_post_returns_none_after_max_retries(
        self, core_client: OceanHttpClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_httpx_client = MagicMock(spec=httpx.AsyncClient)
        mock_httpx_client.post = AsyncMock(side_effect=httpx.ConnectError("failed"))
        monkeypatch.setattr(core_client, "_client", mock_httpx_client)

        result = await core_client.post("http://example.com", json={"test": "data"})

        # Should return None instead of raising
        assert result is None
        # Should have retried 3 times
        assert mock_httpx_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_post_does_not_retry_on_logic_errors(
        self, core_client: OceanHttpClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_httpx_client = MagicMock(spec=httpx.AsyncClient)
        mock_httpx_client.post = AsyncMock(side_effect=TypeError("bad type"))
        monkeypatch.setattr(core_client, "_client", mock_httpx_client)

        result = await core_client.post("http://example.com", json={"test": "data"})

        # Should return None without retrying
        assert result is None
        assert mock_httpx_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_post_logs_warning_on_5xx_errors(
        self, core_client: OceanHttpClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        error_response = MagicMock(spec=httpx.Response)
        error_response.is_error = True
        error_response.status_code = 500
        error_response.text = "server error"
        error_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "500 error", request=MagicMock(), response=error_response
            )
        )

        mock_httpx_client = MagicMock(spec=httpx.AsyncClient)
        mock_httpx_client.post = AsyncMock(return_value=error_response)
        monkeypatch.setattr(core_client, "_client", mock_httpx_client)

        result = await core_client.post("http://example.com", json={"test": "data"})

        # 5xx errors trigger raise_for_status which raises HTTPStatusError (treated as logic error, not retried)
        assert result is None
        assert mock_httpx_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_post_logs_warning_on_4xx_error(
        self, core_client: OceanHttpClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        error_response = MagicMock(spec=httpx.Response)
        error_response.is_error = True
        error_response.status_code = 400
        error_response.text = "bad request"

        mock_httpx_client = MagicMock(spec=httpx.AsyncClient)
        mock_httpx_client.post = AsyncMock(return_value=error_response)
        monkeypatch.setattr(core_client, "_client", mock_httpx_client)

        with patch("port_ocean.clients.core_client.logger") as mock_logger:
            await core_client.post("http://example.com", json={"test": "data"})

        # Should log warning but not retry
        mock_logger.warning.assert_called_once()
        assert mock_httpx_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_post_includes_auth_headers(
        self,
        core_client: OceanHttpClient,
        mock_auth: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_error = False
        mock_response.status_code = 200

        mock_httpx_client = MagicMock(spec=httpx.AsyncClient)
        mock_httpx_client.post = AsyncMock(return_value=mock_response)
        monkeypatch.setattr(core_client, "_client", mock_httpx_client)

        await core_client.post("http://example.com", json={"test": "data"})

        call_kwargs = mock_httpx_client.post.call_args[1]
        assert call_kwargs["headers"] == {"Authorization": "Bearer test-token"}
        mock_auth.headers.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_retries_on_asyncio_timeout(
        self, core_client: OceanHttpClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_error = False
        mock_response.status_code = 200

        mock_httpx_client = MagicMock(spec=httpx.AsyncClient)
        mock_httpx_client.post = AsyncMock(
            side_effect=[asyncio.TimeoutError(), mock_response]
        )
        monkeypatch.setattr(core_client, "_client", mock_httpx_client)

        await core_client.post("http://example.com", json={"test": "data"})

        assert mock_httpx_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_post_retries_on_connection_error(
        self, core_client: OceanHttpClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_error = False
        mock_response.status_code = 200

        mock_httpx_client = MagicMock(spec=httpx.AsyncClient)
        mock_httpx_client.post = AsyncMock(
            side_effect=[ConnectionError("reset"), mock_response]
        )
        monkeypatch.setattr(core_client, "_client", mock_httpx_client)

        await core_client.post("http://example.com", json={"test": "data"})

        assert mock_httpx_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_post_retries_on_os_error(
        self, core_client: OceanHttpClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_error = False
        mock_response.status_code = 200

        mock_httpx_client = MagicMock(spec=httpx.AsyncClient)
        mock_httpx_client.post = AsyncMock(
            side_effect=[OSError("socket error"), mock_response]
        )
        monkeypatch.setattr(core_client, "_client", mock_httpx_client)

        await core_client.post("http://example.com", json={"test": "data"})

        assert mock_httpx_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_post_sleep_delays_double_each_retry(
        self, core_client: OceanHttpClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_sleep = AsyncMock()
        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        mock_httpx_client = MagicMock(spec=httpx.AsyncClient)
        mock_httpx_client.post = AsyncMock(side_effect=httpx.ConnectError("failed"))
        monkeypatch.setattr(core_client, "_client", mock_httpx_client)

        await core_client.post("http://example.com", json={"test": "data"})

        # 3 attempts: sleep after attempt 1 (2s) and attempt 2 (4s), not after 3
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 2
        assert mock_sleep.call_args_list[1][0][0] == 4

    @pytest.mark.asyncio
    async def test_post_propagates_cancelled_error(
        self, core_client: OceanHttpClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_httpx_client = MagicMock(spec=httpx.AsyncClient)
        mock_httpx_client.post = AsyncMock(side_effect=asyncio.CancelledError())
        monkeypatch.setattr(core_client, "_client", mock_httpx_client)

        with pytest.raises(asyncio.CancelledError):
            await core_client.post("http://example.com", json={"test": "data"})

        # Must not retry on cancellation
        assert mock_httpx_client.post.call_count == 1
