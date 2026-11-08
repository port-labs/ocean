from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_integration.foundry.helpers.model_responses_api import (
    fetch_foundry_response,
    response_resource_path,
)


def test_response_resource_path() -> None:
    assert response_resource_path("resp_abc") == "openai/v1/responses/resp_abc"


@pytest.mark.asyncio
async def test_fetch_foundry_response() -> None:
    client = MagicMock()
    client.build_url = MagicMock(
        return_value="https://project/openai/v1/responses/resp_1"
    )
    client.send_api_request = AsyncMock(
        return_value={
            "id": "resp_1",
            "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        }
    )
    with (
        patch(
            "azure_integration.foundry.helpers.model_responses_api.create_foundry_client",
            return_value=client,
        ),
        patch(
            "azure_integration.foundry.helpers.model_responses_api.get_project_endpoint",
            return_value="https://project/",
        ),
    ):
        body = await fetch_foundry_response("resp_1")

    assert body is not None
    assert body["usage"]["input_tokens"] == 1
    client.send_api_request.assert_awaited_once_with(
        "https://project/openai/v1/responses/resp_1", method="GET"
    )
