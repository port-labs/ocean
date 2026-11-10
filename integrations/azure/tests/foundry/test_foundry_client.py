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
    client = FoundryHttpClient(
        get_authorization_header=AsyncMock(return_value={"Authorization": "Bearer x"}),
        api_version="v1",
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
async def test_get_404_returns_empty() -> None:
    client = _client_with_response(404)
    assert await client.send_api_request("https://example/agents/x") == {}


@pytest.mark.asyncio
async def test_post_404_raises() -> None:
    client = _client_with_response(404)
    with pytest.raises(FoundryApiError):
        await client.send_api_request("https://example/agents", method="POST")
