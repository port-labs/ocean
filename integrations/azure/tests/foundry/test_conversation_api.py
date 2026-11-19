from unittest.mock import AsyncMock, MagicMock

import pytest

from azure_integration.foundry.helpers.conversation_api import (
    resolve_conversation_for_invoke,
)

_ENDPOINT = "https://acct.services.ai.azure.com/api/projects/demo"


def _client() -> MagicMock:
    client = MagicMock()
    client.build_url = MagicMock(
        side_effect=lambda endpoint, path: f"{endpoint.rstrip('/')}/{path}"
    )
    client.send_api_request = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_resolve_existing_create_and_metadata() -> None:
    client = _client()
    client.send_api_request.return_value = {"id": "conv_existing"}
    assert (
        await resolve_conversation_for_invoke(
            client, project_endpoint=_ENDPOINT, conversation_id="conv_existing"
        )
        == "conv_existing"
    )
    assert client.send_api_request.await_args.kwargs["method"] == "GET"

    client = _client()
    client.send_api_request.return_value = {"id": "conv_new"}
    assert (
        await resolve_conversation_for_invoke(
            client,
            project_endpoint=_ENDPOINT,
            conversation_id=None,
            metadata={"ticket": "T-1"},
            agent_id="helpful-agent",
        )
        == "conv_new"
    )
    body = client.send_api_request.await_args.kwargs["json_body"]
    assert body["metadata"]["ticket"] == "T-1"
    # agent_id selects protocol path; not stuffed into metadata
    assert client.send_api_request.await_args.args[0].endswith(
        "/protocols/openai/conversations"
    )
