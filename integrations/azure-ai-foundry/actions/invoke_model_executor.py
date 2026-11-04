from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from actions.abstract_executor import AbstractFoundryExecutor
from actions.responses_invoke_mixin import ResponsesInvokeMixin
from helpers.model_responses_api import InvokeModelInputs, build_model_responses_invoke
from webhook_processors.conversation_webhook_processor import ConversationWebhookProcessor
from webhook_processors.registry import WEBHOOK_PATH


class InvokeModelExecutor(AbstractFoundryExecutor, ResponsesInvokeMixin):
    ACTION_NAME = "invoke_model"
    WEBHOOK_PROCESSOR_CLASS = ConversationWebhookProcessor
    WEBHOOK_PATH = WEBHOOK_PATH

    async def execute(self, run: IntegrationRun) -> None:
        inputs = InvokeModelInputs.from_execution_properties(run.execution_properties)
        path, params, body = build_model_responses_invoke(
            model=inputs.deploymentName,
            user_input=inputs.input,
            conversation_id=inputs.conversationId,
            extra_body=inputs.extraBody,
        )
        invoke_url = self.client.build_url(self.project_endpoint, path)
        stream_key = f"{run.id}:{inputs.deploymentName}"
        bind_output = {"deploymentName": inputs.deploymentName}

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
