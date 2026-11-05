from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.actions.responses_invoke_mixin import ResponsesInvokeMixin
from azure_integration.foundry.helpers.conversation_api import resolve_conversation_for_invoke
from azure_integration.foundry.helpers.model_responses_api import InvokeModelInputs, build_model_responses_invoke
from azure_integration.foundry.webhook_processors.conversation_webhook_processor import ConversationWebhookProcessor
from azure_integration.foundry.webhook_processors.registry import WEBHOOK_PATH


class InvokeModelExecutor(AbstractFoundryExecutor, ResponsesInvokeMixin):
    ACTION_NAME = "invoke_model"
    WEBHOOK_PROCESSOR_CLASS = ConversationWebhookProcessor
    WEBHOOK_PATH = WEBHOOK_PATH

    async def execute_foundry(self, run: IntegrationRun) -> None:
        inputs = InvokeModelInputs.from_execution_properties(run.execution_properties)
        try:
            conversation_id = await resolve_conversation_for_invoke(
                self.client,
                conversation_id=inputs.conversationId,
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to resolve conversation: {error}"
            ) from error
        path, params, body = build_model_responses_invoke(
            model=inputs.deploymentName,
            user_input=inputs.input,
            conversation_id=conversation_id,
            extra_body=inputs.extraBody,
        )
        invoke_url = self.client.build_url(self.project_endpoint, path)
        stream_key = f"{run.id}:{inputs.deploymentName}"
        bind_output = {
            "deploymentName": inputs.deploymentName,
            "conversationId": conversation_id,
        }

        await self.execute_responses_invoke(
            run,
            invoke_label=f"Invoking model deployment {inputs.deploymentName}",
            stream_key=stream_key,
            invoke_url=invoke_url,
            params=params,
            body=body,
            agent_id=None,
            bind_output=bind_output,
            complete_on_sse_terminal=True,
        )
