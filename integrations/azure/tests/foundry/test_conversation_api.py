from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from azure_integration.foundry.helpers.conversation_api import (
    resolve_conversation_for_invoke,
)

_ENDPOINT = "https://acct.services.ai.azure.com/api/projects/demo"
_AGENT = "helpful-agent"


def _client() -> MagicMock:
    client = MagicMock()
    client.build_url = MagicMock(
        side_effect=lambda endpoint, path: f"{endpoint.rstrip('/')}/{path}"
    )
    client.send_api_request = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_resolve_verifies_existing_conversation_id() -> None:
    client = _client()
    client.send_api_request.return_value = {"id": "conv_existing"}
    conversation_id = await resolve_conversation_for_invoke(
        client, project_endpoint=_ENDPOINT, conversation_id="conv_existing"
    )
    assert conversation_id == "conv_existing"
    client.send_api_request.assert_awaited_once()
    args, kwargs = client.send_api_request.await_args
    assert kwargs["method"] == "GET"
    assert args[0].endswith("openai/v1/conversations/conv_existing")


@pytest.mark.asyncio
async def test_resolve_creates_conversation_when_id_missing() -> None:
    client = _client()
    client.send_api_request.return_value = {"id": "conv_new"}
    conversation_id = await resolve_conversation_for_invoke(
        client, project_endpoint=_ENDPOINT, conversation_id=None
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
        client,
        project_endpoint=_ENDPOINT,
        conversation_id=None,
        metadata=metadata,
    )
    assert conversation_id == "conv_meta"
    assert client.send_api_request.await_args.kwargs["json_body"] == {
        "metadata": metadata
    }


@pytest.mark.asyncio
async def test_resolve_patches_metadata_on_existing() -> None:
    client = _client()
    client.send_api_request.side_effect = [
        {"id": "conv_existing"},
        {"id": "conv_existing"},
    ]
    conversation_id = await resolve_conversation_for_invoke(
        client,
        project_endpoint=_ENDPOINT,
        conversation_id="conv_existing",
        metadata={"owner": "platform"},
    )
    assert conversation_id == "conv_existing"
    assert client.send_api_request.await_args_list == [
        call(
            f"{_ENDPOINT}/openai/v1/conversations/conv_existing",
            method="GET",
        ),
        call(
            f"{_ENDPOINT}/openai/v1/conversations/conv_existing",
            method="POST",
            json_body={"metadata": {"owner": "platform"}},
        ),
    ]


@pytest.mark.asyncio
async def test_resolve_creates_when_existing_not_found() -> None:
    client = _client()
    client.send_api_request.side_effect = [{}, {"id": "conv_fresh"}]
    conversation_id = await resolve_conversation_for_invoke(
        client,
        project_endpoint=_ENDPOINT,
        conversation_id="conv_stale",
        agent_id=_AGENT,
    )
    assert conversation_id == "conv_fresh"
    get_url = client.send_api_request.await_args_list[0].args[0]
    create_url = client.send_api_request.await_args_list[1].args[0]
    assert get_url.endswith(
        f"agents/{_AGENT}/endpoint/protocols/openai/conversations/conv_stale"
    )
    assert create_url.endswith(
        f"agents/{_AGENT}/endpoint/protocols/openai/conversations"
    )
    assert client.send_api_request.await_args_list[1].kwargs["method"] == "POST"


@pytest.mark.asyncio
async def test_resolve_agent_create_uses_protocol_path() -> None:
    client = _client()
    client.send_api_request.return_value = {"id": "conv_agent"}
    conversation_id = await resolve_conversation_for_invoke(
        client,
        project_endpoint=_ENDPOINT,
        conversation_id=None,
        agent_id=_AGENT,
    )
    assert conversation_id == "conv_agent"
    assert client.send_api_request.await_args.args[0].endswith(
        f"agents/{_AGENT}/endpoint/protocols/openai/conversations"
    )


@pytest.mark.asyncio
async def test_resolve_strips_blank_conversation_id() -> None:
    client = _client()
    client.send_api_request.return_value = {"id": "conv_blank"}
    conversation_id = await resolve_conversation_for_invoke(
        client, project_endpoint=_ENDPOINT, conversation_id="   "
    )
    assert conversation_id == "conv_blank"
    assert client.send_api_request.await_args.kwargs["method"] == "POST"


@pytest.mark.asyncio
async def test_resolve_create_raises_on_unexpected_response() -> None:
    client = _client()
    client.send_api_request.return_value = {"ok": True}
    with pytest.raises(RuntimeError, match="Unexpected create conversation"):
        await resolve_conversation_for_invoke(
            client, project_endpoint=_ENDPOINT, conversation_id=None
        )
