from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.actions.responses_invoke_mixin import (
    ResponsesInvokeMixin,
)
from azure_integration.foundry.helpers.conversation_api import (
    resolve_conversation_for_invoke,
)
from azure_integration.foundry.helpers.model_responses_api import (
    InvokeModelInputs,
    build_model_responses_invoke,
)


class InvokeModelExecutor(AbstractFoundryExecutor, ResponsesInvokeMixin):
    ACTION_NAME = "invoke_model"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = InvokeModelInputs.from_execution_properties(run.execution_properties)
        project_endpoint = inputs.project_endpoint
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
        path, body = build_model_responses_invoke(
            model=inputs.deploymentName,
            user_input=inputs.input,
            conversation_id=conversation_id,
            extra_body=inputs.extraBody,
        )
        invoke_url = self.client.build_url(project_endpoint, path)
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
        )
