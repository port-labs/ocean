from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Optional

import pytest

from gcp_core.cloud_function.client import CloudFunctionClient

_MODULE = "gcp_core.cloud_function.client"


def _make_client(
    token: Optional[str] = "test-token",
    function_url: str = "https://example.run.app/sync",
    secrets: dict | None = None,
    max_retries: int = 3,
    timeout: float = 60.0,
) -> CloudFunctionClient:
    async def token_supplier() -> Optional[str]:
        return token

    return CloudFunctionClient(
        agent="gcp/test-integration",
        function_url=function_url,
        secrets=secrets or {},
        token_supplier=token_supplier,
        max_retries=max_retries,
        timeout=timeout,
    )


def _mock_post(response_body: dict) -> tuple[MagicMock, AsyncMock]:
    """Return (mock_http_client, mock_post) configured to return response_body."""
    mock_response = MagicMock()
    mock_response.is_error = False
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = response_body
    mock_http = MagicMock()
    mock_http.post = AsyncMock(return_value=mock_response)
    return mock_http, mock_http.post


@pytest.mark.asyncio
async def test_sync_single_page_no_more() -> None:
    mock_http, mock_post = _mock_post(
        {"insert": [{"id": "1"}, {"id": "2"}], "hasMore": False, "state": None}
    )
    client = _make_client()

    with patch(f"{_MODULE}.http_async_client", mock_http):
        pages = [page async for page in client.sync("employee")]

    assert pages == [[{"id": "1"}, {"id": "2"}]]
    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert payload["kind"] == "employee"
    assert payload["state"] is None
    assert payload["agent"] == "gcp/test-integration"


@pytest.mark.asyncio
async def test_sync_pagination_passes_state() -> None:
    page1 = MagicMock()
    page1.is_error = False
    page1.raise_for_status = MagicMock()
    page1.json.return_value = {
        "insert": [{"id": "1"}],
        "hasMore": True,
        "state": {"cursor": "page-2"},
    }
    page2 = MagicMock()
    page2.is_error = False
    page2.raise_for_status = MagicMock()
    page2.json.return_value = {
        "insert": [{"id": "2"}],
        "hasMore": False,
        "state": None,
    }
    mock_http = MagicMock()
    mock_http.post = AsyncMock(side_effect=[page1, page2])

    with patch(f"{_MODULE}.http_async_client", mock_http):
        pages = [page async for page in _make_client().sync("employee")]

    assert pages == [[{"id": "1"}], [{"id": "2"}]]
    assert mock_http.post.call_count == 2
    second_payload = mock_http.post.call_args_list[1].kwargs["json"]
    assert second_payload["state"] == {"cursor": "page-2"}


@pytest.mark.asyncio
async def test_sync_skips_empty_pages() -> None:
    mock_http, _ = _mock_post({"insert": [], "hasMore": False, "state": None})

    with patch(f"{_MODULE}.http_async_client", mock_http):
        pages = [page async for page in _make_client().sync("employee")]

    assert pages == []


@pytest.mark.asyncio
async def test_sync_stops_when_state_does_not_advance() -> None:
    """Endpoint returning hasMore=true with unchanged state must not loop forever."""
    stuck_page = MagicMock()
    stuck_page.is_error = False
    stuck_page.raise_for_status = MagicMock()
    stuck_page.json.return_value = {
        "insert": [{"id": "1"}],
        "hasMore": True,
        "state": None,  # state never advances
    }
    mock_http = MagicMock()
    mock_http.post = AsyncMock(return_value=stuck_page)

    with patch(f"{_MODULE}.http_async_client", mock_http), patch(
        f"{_MODULE}.logger"
    ) as mock_logger:
        pages = [page async for page in _make_client().sync("employee")]

    assert pages == [[{"id": "1"}]]
    assert mock_http.post.call_count == 1
    mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_sends_bearer_token() -> None:
    mock_http, mock_post = _mock_post({"insert": [], "hasMore": False, "state": None})

    with patch(f"{_MODULE}.http_async_client", mock_http):
        async for _ in _make_client(token="my-id-token").sync("employee"):
            pass

    headers = mock_post.call_args.kwargs["headers"]
    assert headers == {"Authorization": "Bearer my-id-token"}


@pytest.mark.asyncio
async def test_fetch_omits_auth_header_when_no_token() -> None:
    mock_http, mock_post = _mock_post({"insert": [], "hasMore": False, "state": None})

    with patch(f"{_MODULE}.http_async_client", mock_http):
        async for _ in _make_client(token=None).sync("employee"):
            pass

    headers = mock_post.call_args.kwargs["headers"]
    assert headers == {}


@pytest.mark.asyncio
async def test_fetch_forwards_secrets() -> None:
    mock_http, mock_post = _mock_post({"insert": [], "hasMore": False, "state": None})

    with patch(f"{_MODULE}.http_async_client", mock_http):
        async for _ in _make_client(secrets={"hibobToken": "abc123"}).sync("employee"):
            pass

    payload = mock_post.call_args.kwargs["json"]
    assert payload["secrets"] == {"hibobToken": "abc123"}


@pytest.mark.asyncio
async def test_fetch_raises_on_http_error() -> None:
    import httpx

    mock_response = MagicMock()
    mock_response.is_error = True
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Server Error", request=MagicMock(), response=MagicMock()
    )
    mock_http = MagicMock()
    mock_http.post = AsyncMock(return_value=mock_response)

    with patch(f"{_MODULE}.http_async_client", mock_http):
        with pytest.raises(httpx.HTTPStatusError):
            async for _ in _make_client().sync("employee"):
                pass


@pytest.mark.asyncio
async def test_fetch_logs_error_before_raising() -> None:
    import httpx

    mock_response = MagicMock()
    mock_response.is_error = True
    mock_response.status_code = 503
    mock_response.text = "Service Unavailable"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503 Error", request=MagicMock(), response=MagicMock()
    )
    mock_http = MagicMock()
    mock_http.post = AsyncMock(return_value=mock_response)

    with patch(f"{_MODULE}.http_async_client", mock_http), patch(
        f"{_MODULE}.logger"
    ) as mock_logger:
        with pytest.raises(httpx.HTTPStatusError):
            async for _ in _make_client().sync("employee"):
                pass

    mock_logger.error.assert_called_once()
    logged = mock_logger.error.call_args[0][0]
    assert "503" in logged
    assert "Service Unavailable" in logged


@pytest.mark.asyncio
async def test_retries_on_429_then_succeeds() -> None:
    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.is_error = True
    rate_limited.headers = {"Retry-After": "0"}
    rate_limited.raise_for_status = MagicMock()

    success = MagicMock()
    success.status_code = 200
    success.is_error = False
    success.raise_for_status = MagicMock()
    success.json.return_value = {"insert": [{"id": "1"}], "hasMore": False, "state": None}

    mock_http = MagicMock()
    mock_http.post = AsyncMock(side_effect=[rate_limited, success])

    with patch(f"{_MODULE}.http_async_client", mock_http), \
         patch(f"{_MODULE}.asyncio.sleep") as mock_sleep:
        pages = [page async for page in _make_client(max_retries=1).sync("employee")]

    assert pages == [[{"id": "1"}]]
    assert mock_http.post.call_count == 2
    mock_sleep.assert_called_once_with(0.0)


@pytest.mark.asyncio
async def test_exhausts_retries_and_raises() -> None:
    import httpx

    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.is_error = True
    rate_limited.headers = {"Retry-After": "0"}
    rate_limited.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Too Many Requests", request=MagicMock(), response=MagicMock()
    )

    mock_http = MagicMock()
    mock_http.post = AsyncMock(return_value=rate_limited)

    with patch(f"{_MODULE}.http_async_client", mock_http), \
         patch(f"{_MODULE}.asyncio.sleep"):
        with pytest.raises(httpx.HTTPStatusError):
            async for _ in _make_client(max_retries=2).sync("employee"):
                pass

    assert mock_http.post.call_count == 3  # 1 initial + 2 retries


@pytest.mark.asyncio
async def test_respects_retry_after_header() -> None:
    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.is_error = True
    rate_limited.headers = {"Retry-After": "42"}
    rate_limited.raise_for_status = MagicMock()

    success = MagicMock()
    success.status_code = 200
    success.is_error = False
    success.raise_for_status = MagicMock()
    success.json.return_value = {"insert": [], "hasMore": False, "state": None}

    mock_http = MagicMock()
    mock_http.post = AsyncMock(side_effect=[rate_limited, success])

    with patch(f"{_MODULE}.http_async_client", mock_http), \
         patch(f"{_MODULE}.asyncio.sleep") as mock_sleep:
        async for _ in _make_client(max_retries=1).sync("employee"):
            pass

    mock_sleep.assert_called_once_with(42.0)
