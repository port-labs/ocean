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
from azure_integration.foundry.core.exporters.model_deployments_exporter import (
    ModelDeploymentsExporter,
)
from azure_integration.foundry.core.options import SingleModelDeploymentOptions
from azure_integration.foundry.helpers.conversation_api import (
    resolve_conversation_for_invoke,
)


class InvokeModelInputs(AbstractFoundryInvokeInput):
    deploymentName: str = Field(min_length=1)
    input: str = Field(min_length=1)
    conversationId: str | None = None
    extraBody: dict[str, Any] = Field(default_factory=dict)


def _supports_chat(deployment: dict[str, Any]) -> bool:
    caps = deployment.get("capabilities")
    if not isinstance(caps, dict):
        return False
    return str(caps.get("chat_completion", "")).lower() == "true"


class InvokeModelExecutor(AbstractFoundryExecutor, ResponsesInvokeMixin):
    ACTION_NAME = "invoke_model"

    def __init__(self) -> None:
        super().__init__()
        ResponsesInvokeMixin.__init__(self, self.client)

    async def execute(self, run: IntegrationRun) -> None:
        inputs = InvokeModelInputs.from_execution_properties(run.execution_properties)
        project_endpoint = inputs.project_endpoint
        deployment = await ModelDeploymentsExporter(self.client).get_resource(
            SingleModelDeploymentOptions(
                project_endpoint=project_endpoint,
                project_id=inputs.projectArmId,
                deployment_name=inputs.deploymentName,
            )
        )
        if deployment is None:
            raise ActionExecutionError(
                f"Model deployment '{inputs.deploymentName}' not found on this project"
            )
        if not _supports_chat(deployment):
            raise ActionExecutionError(
                f"Deployment '{inputs.deploymentName}' does not support chat "
                f"(capabilities.chat_completion is not true). "
                "invoke_model uses openai/v1/responses and only works with chat-capable "
                "model deployments. Decision models use /providers/microsoft/v1/systemone."
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
                "projectEndpoint": project_endpoint,
            },
            complete_on_sse_terminal=True,
            running_status_label=MODEL_RUNNING_STATUS_LABEL,
        )
