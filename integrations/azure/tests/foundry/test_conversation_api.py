from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from azure_integration.foundry.helpers.conversation_api import (
    resolve_conversation_for_invoke,
)


def _client() -> MagicMock:
    client = MagicMock()
    client.build_url = MagicMock(
        side_effect=lambda endpoint, path: f"{endpoint.rstrip('/')}/{path}"
    )
    client.send_api_request = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_resolve_reuses_existing_conversation_id() -> None:
    client = _client()
    conversation_id = await resolve_conversation_for_invoke(
        client, conversation_id="conv_existing"
    )
    assert conversation_id == "conv_existing"
    client.send_api_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_creates_conversation_when_id_missing() -> None:
    client = _client()
    client.send_api_request.return_value = {"id": "conv_new"}
    conversation_id = await resolve_conversation_for_invoke(
        client, conversation_id=None
    )
    assert conversation_id == "conv_new"
    client.send_api_request.assert_awaited_once()
    args, kwargs = client.send_api_request.await_args
    assert kwargs["method"] == "POST"
    assert kwargs["json_body"] == {}
    assert args[0].endswith("openai/v1/conversations")


@pytest.mark.asyncio
async def test_resolve_create_includes_metadata() -> None:
    client = _client()
    client.send_api_request.return_value = {"id": "conv_meta"}
    metadata: dict[str, Any] = {"subject": "ticket-1"}
    conversation_id = await resolve_conversation_for_invoke(
        client, conversation_id=None, metadata=metadata
    )
    assert conversation_id == "conv_meta"
    assert client.send_api_request.await_args.kwargs["json_body"] == {
        "metadata": metadata
    }


@pytest.mark.asyncio
async def test_resolve_patches_metadata_on_existing() -> None:
    client = _client()
    conversation_id = await resolve_conversation_for_invoke(
        client,
        conversation_id="conv_existing",
        metadata={"owner": "platform"},
    )
    assert conversation_id == "conv_existing"
    args, kwargs = client.send_api_request.await_args
    assert kwargs["method"] == "POST"
    assert args[0].endswith("openai/v1/conversations/conv_existing")
    assert kwargs["json_body"] == {"metadata": {"owner": "platform"}}


@pytest.mark.asyncio
async def test_resolve_create_raises_on_unexpected_response() -> None:
    client = _client()
    client.send_api_request.return_value = {"ok": True}
    with pytest.raises(RuntimeError, match="Unexpected create conversation"):
        await resolve_conversation_for_invoke(client, conversation_id=None)
