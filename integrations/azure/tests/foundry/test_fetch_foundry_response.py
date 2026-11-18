from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_integration.foundry.helpers.model_responses_api import fetch_foundry_response

_ENDPOINT = "https://acct.services.ai.azure.com/api/projects/demo"


@pytest.mark.asyncio
async def test_fetch_tries_agent_protocol_path_first() -> None:
    client = MagicMock()
    client.build_url = MagicMock(side_effect=lambda ep, path: f"{ep}/{path}")
    client.send_api_request = AsyncMock(
        side_effect=[
            {"id": "resp_1", "status": "completed", "usage": {"input_tokens": 1}},
        ]
    )
    with patch(
        "azure_integration.foundry.helpers.model_responses_api.create_foundry_client",
        return_value=client,
    ):
        body = await fetch_foundry_response(
            "resp_1", project_endpoint=_ENDPOINT, agent_id="agent-1"
        )
    assert body is not None
    assert body["id"] == "resp_1"
    first_path = client.build_url.call_args_list[0].args[1]
    assert first_path.endswith(
        "agents/agent-1/endpoint/protocols/openai/responses/resp_1"
    )
    client.send_api_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_falls_back_to_project_responses_path() -> None:
    client = MagicMock()
    client.build_url = MagicMock(side_effect=lambda ep, path: f"{ep}/{path}")
    client.send_api_request = AsyncMock(
        side_effect=[
            RuntimeError("404 agent path"),
            {"id": "resp_1", "status": "completed"},
        ]
    )
    with patch(
        "azure_integration.foundry.helpers.model_responses_api.create_foundry_client",
        return_value=client,
    ):
        body = await fetch_foundry_response(
            "resp_1", project_endpoint=_ENDPOINT, agent_id="agent-1"
        )
    assert body == {"id": "resp_1", "status": "completed"}
    assert client.send_api_request.await_count == 2
    second_path = client.build_url.call_args_list[1].args[1]
    assert second_path.endswith("openai/v1/responses/resp_1")
