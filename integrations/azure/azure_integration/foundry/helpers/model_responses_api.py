from __future__ import annotations

from typing import Any

from loguru import logger
from pydantic import Field

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryInvokeInput,
)
from azure_integration.foundry.clients.http.foundry_client import create_foundry_client


async def fetch_foundry_response(
    response_id: str,
    *,
    project_endpoint: str,
    agent_id: str | None = None,
) -> dict[str, Any] | None:
    """GET a stored Responses body. Agent invokes: try agent protocol path first."""
    from azure_integration.foundry.helpers.utils import agent_openai_protocol_path

    client = create_foundry_client()
    paths: list[str] = []
    if agent_id and agent_id.strip():
        paths.append(
            f"{agent_openai_protocol_path(agent_id.strip(), 'responses')}/{response_id}"
        )
    paths.append(f"openai/v1/responses/{response_id}")

    last_error: Exception | None = None
    for path in paths:
        url = client.build_url(project_endpoint, path)
        try:
            payload = await client.send_api_request(url, method="GET")
        except Exception as error:
            last_error = error
            continue
        if isinstance(payload, dict) and payload:
            return payload
    if last_error is not None:
        logger.warning(f"Failed to GET Foundry response {response_id}: {last_error}")
    return None


def build_model_responses_invoke(
    *,
    model: str,
    user_input: str,
    conversation_id: str | None = None,
    extra_body: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return (path, json_body) for generic ``openai/v1/responses`` invoke."""
    body: dict[str, Any] = {"model": model, "input": user_input, **(extra_body or {})}
    if conversation_id:
        body.setdefault("conversation", conversation_id)
    return "openai/v1/responses", body


class InvokeModelInputs(AbstractFoundryInvokeInput):
    deploymentName: str = Field(min_length=1)
    input: str = Field(min_length=1)
    conversationId: str | None = None
    extraBody: dict[str, Any] = Field(default_factory=dict)
