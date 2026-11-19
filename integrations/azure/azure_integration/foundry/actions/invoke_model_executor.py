from typing import Any

from pydantic import Field
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryInvokeInput,
)
from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.actions.responses_invoke_mixin import (
    MODEL_RUNNING_STATUS_LABEL,
    ResponsesInvokeMixin,
)
from azure_integration.foundry.clients.http.foundry_client import (
    FoundryApiError,
    FoundryHttpClient,
)
from azure_integration.foundry.helpers.conversation_api import (
    resolve_conversation_for_invoke,
)


class InvokeModelInputs(AbstractFoundryInvokeInput):
    deploymentName: str = Field(min_length=1)
    input: str = Field(min_length=1)
    conversationId: str | None = None
    extraBody: dict[str, Any] = Field(default_factory=dict)


def _chat_completion_enabled(capabilities: Any) -> bool:
    if not isinstance(capabilities, dict):
        return False
    return str(capabilities.get("chat_completion", "")).lower() == "true"


async def ensure_chat_model_deployment(
    client: FoundryHttpClient,
    *,
    project_endpoint: str,
    deployment_name: str,
) -> None:
    """Reject non-chat deploys (e.g. Decision/SystemOne) before Responses invoke."""
    url = client.build_url(project_endpoint, f"deployments/{deployment_name}")
    try:
        payload = await client.send_api_request(url, method="GET")
    except FoundryApiError as error:
        if error.status_code == 404:
            raise ActionExecutionError(
                f"Model deployment '{deployment_name}' not found on this project"
            ) from error
        raise ActionExecutionError(
            f"Failed to load model deployment '{deployment_name}': {error}"
        ) from error
    if not isinstance(payload, dict) or not payload.get("name"):
        raise ActionExecutionError(
            f"Model deployment '{deployment_name}' not found on this project"
        )
    if _chat_completion_enabled(payload.get("capabilities")):
        return
    raise ActionExecutionError(
        f"Deployment '{deployment_name}' does not support chat "
        f"(capabilities.chat_completion is not true). "
        "invoke_model uses openai/v1/responses and only works with chat-capable "
        "model deployments. Decision models use /providers/microsoft/v1/systemone."
    )


class InvokeModelExecutor(AbstractFoundryExecutor, ResponsesInvokeMixin):
    ACTION_NAME = "invoke_model"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = InvokeModelInputs.from_execution_properties(run.execution_properties)
        project_endpoint = inputs.project_endpoint
        await ensure_chat_model_deployment(
            self.client,
            project_endpoint=project_endpoint,
            deployment_name=inputs.deploymentName,
        )
        try:
            conversation_id = await resolve_conversation_for_invoke(
                self.client,
                project_endpoint=project_endpoint,
                conversation_id=inputs.conversationId,
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to resolve conversation: {error}"
            ) from error
        body: dict[str, Any] = {
            "model": inputs.deploymentName,
            "input": inputs.input,
            **inputs.extraBody,
        }
        if conversation_id:
            body.setdefault("conversation", conversation_id)
        invoke_url = self.client.build_url(project_endpoint, "openai/v1/responses")
        await self.execute_responses_invoke(
            run,
            invoke_label=f"Invoking model deployment {inputs.deploymentName}",
            stream_key=f"{run.id}:{inputs.deploymentName}",
            invoke_url=invoke_url,
            body=body,
            bind_output={
                "conversationId": conversation_id,
                "projectArmId": inputs.projectArmId,
            },
            complete_on_sse_terminal=True,
            running_status_label=MODEL_RUNNING_STATUS_LABEL,
        )
