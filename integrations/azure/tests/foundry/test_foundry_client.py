from unittest.mock import AsyncMock, MagicMock

import pytest

from azure_integration.foundry.clients.http.foundry_client import (
    FoundryApiError,
    FoundryHttpClient,
)


def test_items_from_payload_data_key() -> None:
    payload = {"data": [{"id": "1"}, {"id": "2"}]}
    assert len(FoundryHttpClient.items_from_payload(payload)) == 2


def test_items_from_payload_list() -> None:
    payload = [{"id": "a"}]
    assert FoundryHttpClient.items_from_payload(payload)[0]["id"] == "a"


def test_openai_routes_skip_api_version() -> None:
    url = "https://x.services.ai.azure.com/api/projects/p/openai/v1/conversations"
    assert FoundryHttpClient.uses_openai_compatible_routes(url) is True
    assert (
        FoundryHttpClient.uses_openai_compatible_routes(
            "https://x.services.ai.azure.com/api/projects/p/agents"
        )
        is False
    )
    assert (
        FoundryHttpClient.uses_openai_compatible_routes(
            "https://x.services.ai.azure.com/api/projects/p/agents/a/endpoint/protocols/openai/responses"
        )
        is False
    )


def _client_with_response(status_code: int) -> FoundryHttpClient:
    client = FoundryHttpClient(api_version="v1")
    client._authorization_headers = AsyncMock(  # type: ignore[method-assign]
        return_value={"Authorization": "Bearer x"}
    )
    response = MagicMock()
    response.status_code = status_code
    response.is_error = status_code >= 400
    response.text = "not found"
    response.reason_phrase = "Not Found"
    response.content = b""
    client._http.request = AsyncMock(return_value=response)  # type: ignore[method-assign]
    return client


@pytest.mark.asyncio
async def test_get_404_raises() -> None:
    client = _client_with_response(404)
    with pytest.raises(FoundryApiError) as exc_info:
        await client.send_api_request("https://example/agents/x")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_bytes_get_404_returns_empty() -> None:
    client = _client_with_response(404)
    assert await client.send_bytes_request("https://example/skills/x/content") == b""


@pytest.mark.asyncio
async def test_bytes_get_returns_content() -> None:
    client = FoundryHttpClient(api_version="v1")
    client._authorization_headers = AsyncMock(  # type: ignore[method-assign]
        return_value={"Authorization": "Bearer x"}
    )
    response = MagicMock()
    response.status_code = 200
    response.is_error = False
    response.content = b"PK\x03\x04zip"
    client._http.request = AsyncMock(return_value=response)  # type: ignore[method-assign]
    assert await client.send_bytes_request("https://example/skills/x/content") == (
        b"PK\x03\x04zip"
    )


@pytest.mark.asyncio
async def test_post_404_raises() -> None:
    client = _client_with_response(404)
    with pytest.raises(FoundryApiError):
        await client.send_api_request("https://example/agents", method="POST")


@pytest.mark.asyncio
async def test_open_responses_stream_uses_stream_http_client() -> None:
    client = FoundryHttpClient(api_version="v1")
    client._authorization_headers = AsyncMock(  # type: ignore[method-assign]
        return_value={"Authorization": "Bearer x"}
    )
    response = MagicMock()
    response.is_error = False
    response.status_code = 200
    built = MagicMock(name="request")
    client._stream_http.build_request = MagicMock(return_value=built)  # type: ignore[method-assign]
    client._stream_http.send = AsyncMock(return_value=response)  # type: ignore[method-assign]
    client._http.send = AsyncMock()  # type: ignore[method-assign]

    got = await client.open_responses_stream(
        "https://example/openai/v1/responses",
        {"input": "hi", "background": True},
    )

    assert got is response
    build_kwargs = client._stream_http.build_request.call_args.kwargs
    assert build_kwargs["json"]["stream"] is True
    client._stream_http.send.assert_awaited_once_with(built, stream=True)
    client._http.send.assert_not_called()


@pytest.mark.asyncio
async def test_open_responses_stream_error_reads_body_then_closes() -> None:
    client = FoundryHttpClient(api_version="v1")
    client._authorization_headers = AsyncMock(  # type: ignore[method-assign]
        return_value={"Authorization": "Bearer x"}
    )
    response = MagicMock()
    response.is_error = True
    response.status_code = 400
    response.text = "bad request"
    response.reason_phrase = "Bad Request"
    response.aread = AsyncMock()
    response.aclose = AsyncMock()
    client._stream_http.build_request = MagicMock(  # type: ignore[method-assign]
        return_value=MagicMock()
    )
    client._stream_http.send = AsyncMock(return_value=response)  # type: ignore[method-assign]

    with pytest.raises(FoundryApiError, match="bad request"):
        await client.open_responses_stream(
            "https://example/openai/v1/responses",
            {"input": "hi"},
        )

    response.aread.assert_awaited_once()
    response.aclose.assert_awaited_once()
