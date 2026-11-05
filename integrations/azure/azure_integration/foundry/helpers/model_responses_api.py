from __future__ import annotations

from typing import Any

from loguru import logger
from pydantic import Field

from azure_integration.foundry.actions.abstract_action_input import AbstractFoundryActionInput
from azure_integration.foundry.clients.client_factory import create_foundry_client
from azure_integration.foundry.helpers.project_scope import get_project_endpoint


def response_resource_path(response_id: str) -> str:
    return f"openai/v1/responses/{response_id}"


async def fetch_foundry_response(response_id: str) -> dict[str, Any] | None:
    client = create_foundry_client()
    url = client.build_url(
        get_project_endpoint(), response_resource_path(response_id)
    )
    try:
        payload = await client.send_api_request(url, method="GET")
    except Exception as error:
        logger.warning(f"Failed to GET Foundry response {response_id}: {error}")
        return None
    if isinstance(payload, dict) and payload:
        return payload
    return None


def build_model_responses_invoke(
    *,
    model: str,
    user_input: str,
    conversation_id: str | None = None,
    extra_body: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Return (path, query_params, json_body) for generic ``openai/v1/responses`` invoke."""
    path = "openai/v1/responses"
    body: dict[str, Any] = {"model": model, "input": user_input, **(extra_body or {})}
    if conversation_id:
        body.setdefault("conversation", conversation_id)
    return path, {}, body


class InvokeModelInputs(AbstractFoundryActionInput):
    deploymentName: str = Field(min_length=1)
    input: str = Field(min_length=1)
    conversationId: str | None = None
    extraBody: dict[str, Any] = Field(default_factory=dict)
