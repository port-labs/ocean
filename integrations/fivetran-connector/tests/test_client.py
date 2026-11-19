from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional

import pytest

from fivetran_connector.client import FivetranClient

_MODULE = "fivetran_connector.client"


def _make_client(
    token: Optional[str] = "test-token",
    function_url: str = "https://example.run.app/sync",
    secrets: dict | None = None,
) -> FivetranClient:
    async def token_supplier() -> Optional[str]:
        return token

    return FivetranClient(
        agent="fivetran-connector/test-integration",
        function_url=function_url,
        secrets=secrets or {},
        token_supplier=token_supplier,
    )


def _fivetran_response(
    table: str,
    rows: list,
    has_more: bool = False,
    state: dict | None = None,
) -> dict:
    return {
        "insert": {table: rows},
        "delete": {},
        "hasMore": has_more,
        "state": state or {table: ""},
    }


def _mock_post(response_body: dict) -> tuple[MagicMock, AsyncMock]:
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
        _fivetran_response("employee", [{"id": "1"}, {"id": "2"}])
    )

    with patch(f"{_MODULE}.http_async_client", mock_http):
        pages = [page async for page in _make_client().sync("employee")]

    assert pages == [[{"id": "1"}, {"id": "2"}]]
    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert payload["state"] == {}
    assert payload["agent"] == "fivetran-connector/test-integration"
    assert "kind" not in payload


@pytest.mark.asyncio
async def test_sync_pagination_passes_state() -> None:
    page1 = MagicMock()
    page1.is_error = False
    page1.raise_for_status = MagicMock()
    page1.json.return_value = _fivetran_response(
        "employee", [{"id": "1"}], has_more=True, state={"employee": "page-2"}
    )
    page2 = MagicMock()
    page2.is_error = False
    page2.raise_for_status = MagicMock()
    page2.json.return_value = _fivetran_response("employee", [{"id": "2"}])
    mock_http = MagicMock()
    mock_http.post = AsyncMock(side_effect=[page1, page2])

    with patch(f"{_MODULE}.http_async_client", mock_http):
        pages = [page async for page in _make_client().sync("employee")]

    assert pages == [[{"id": "1"}], [{"id": "2"}]]
    assert mock_http.post.call_count == 2
    second_payload = mock_http.post.call_args_list[1].kwargs["json"]
    assert second_payload["state"] == {"employee": "page-2"}


@pytest.mark.asyncio
async def test_sync_skips_empty_pages() -> None:
    mock_http, _ = _mock_post(_fivetran_response("employee", []))

    with patch(f"{_MODULE}.http_async_client", mock_http):
        pages = [page async for page in _make_client().sync("employee")]

    assert pages == []


@pytest.mark.asyncio
async def test_sync_extracts_correct_table() -> None:
    mock_http, _ = _mock_post(
        {
            "insert": {
                "employee": [{"id": "1"}],
                "department": [{"id": "dept-1"}],
            },
            "hasMore": False,
            "state": {},
        }
    )

    with patch(f"{_MODULE}.http_async_client", mock_http):
        pages = [page async for page in _make_client().sync("employee")]

    assert pages == [[{"id": "1"}]]


@pytest.mark.asyncio
async def test_fetch_sends_bearer_token() -> None:
    mock_http, mock_post = _mock_post(_fivetran_response("employee", []))

    with patch(f"{_MODULE}.http_async_client", mock_http):
        async for _ in _make_client(token="my-id-token").sync("employee"):
            pass

    assert mock_post.call_args.kwargs["headers"] == {
        "Authorization": "Bearer my-id-token"
    }


@pytest.mark.asyncio
async def test_fetch_omits_auth_header_when_no_token() -> None:
    mock_http, mock_post = _mock_post(_fivetran_response("employee", []))

    with patch(f"{_MODULE}.http_async_client", mock_http):
        async for _ in _make_client(token=None).sync("employee"):
            pass

    assert mock_post.call_args.kwargs["headers"] == {}


@pytest.mark.asyncio
async def test_fetch_forwards_secrets() -> None:
    mock_http, mock_post = _mock_post(_fivetran_response("employee", []))

    with patch(f"{_MODULE}.http_async_client", mock_http):
        async for _ in _make_client(secrets={"apiToken": "abc123"}).sync("employee"):
            pass

    assert mock_post.call_args.kwargs["json"]["secrets"] == {"apiToken": "abc123"}


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
