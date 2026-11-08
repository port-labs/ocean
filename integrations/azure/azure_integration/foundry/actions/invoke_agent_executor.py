from typing import Any

from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryActionInput,
)
from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.actions.responses_invoke_mixin import (
    ResponsesInvokeMixin,
)
from azure_integration.foundry.helpers.agent_api import build_agent_responses_invoke
from azure_integration.foundry.helpers.conversation_api import (
    resolve_conversation_for_invoke,
)
from azure_integration.foundry.webhook_processors.abstract_webhook_processor import (
    WEBHOOK_PATH,
)
from azure_integration.foundry.webhook_processors.conversation_webhook_processor import (
    ConversationWebhookProcessor,
)


class InvokeAgentInputs(AbstractFoundryActionInput):
    agentId: str = Field(min_length=1)
    input: str = Field(min_length=1)
    conversationId: str | None = None
    conversationMetadata: dict[str, Any] | None = None
    reportInvocationStatus: bool = Field(default=True)
    extraBody: dict[str, Any] = Field(default_factory=dict)


class InvokeAgentExecutor(AbstractFoundryExecutor, ResponsesInvokeMixin):
    ACTION_NAME = "invoke_agent"
    WEBHOOK_PROCESSOR_CLASS = ConversationWebhookProcessor
    WEBHOOK_PATH = WEBHOOK_PATH

    async def execute_foundry(self, run: IntegrationRun) -> None:
        inputs = InvokeAgentInputs.from_execution_properties(run.execution_properties)
        try:
            conversation_id = await resolve_conversation_for_invoke(
                self.client,
                conversation_id=inputs.conversationId,
                metadata=inputs.conversationMetadata,
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to resolve conversation: {error}"
            ) from error
        path, params, body = build_agent_responses_invoke(
            agent_id=inputs.agentId,
            user_input=inputs.input,
            conversation_id=conversation_id,
            extra_body=inputs.extraBody,
        )
        invoke_url = self.client.build_url(self.project_endpoint, path)
        await self.execute_responses_invoke(
            run,
            invoke_label=f"Invoking Foundry agent {inputs.agentId}",
            stream_key=f"{run.id}:{inputs.agentId}",
            invoke_url=invoke_url,
            params=params,
            body=body,
            agent_id=inputs.agentId,
            bind_output={
                "agentId": inputs.agentId,
                "conversationId": conversation_id,
            },
            report_invocation_status=inputs.reportInvocationStatus,
            early_complete_on_bind=not inputs.reportInvocationStatus,
        )
