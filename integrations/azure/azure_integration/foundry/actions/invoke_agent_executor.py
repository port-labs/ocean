from typing import Any

from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from azure_integration.foundry.actions.abstract_action_input import AbstractFoundryActionInput
from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.actions.responses_invoke_mixin import ResponsesInvokeMixin
from azure_integration.foundry.helpers.agent_api import build_agent_responses_invoke
from azure_integration.foundry.helpers.conversation_api import resolve_conversation_for_invoke
from azure_integration.foundry.helpers.port_mcp import ensure_port_mcp_on_agent, remint_port_mcp_for_invoke
from azure_integration.foundry.webhook_processors.conversation_webhook_processor import ConversationWebhookProcessor
from azure_integration.foundry.webhook_processors.registry import WEBHOOK_PATH

# Invoke-time Port MCP (ensure connection + remint) stays off until re-enabled deliberately.
_INVOKE_AGENT_PORT_MCP_ENABLED = False


class InvokeAgentInputs(AbstractFoundryActionInput):
    agentId: str = Field(min_length=1)
    input: str = Field(min_length=1)
    conversationId: str | None = None
    conversationMetadata: dict[str, Any] | None = None
    enablePortMcp: bool = Field(default=True)
    reportInvocationStatus: bool = Field(default=True)
    extraBody: dict[str, Any] = Field(default_factory=dict)


class InvokeAgentExecutor(AbstractFoundryExecutor, ResponsesInvokeMixin):
    ACTION_NAME = "invoke_agent"
    WEBHOOK_PROCESSOR_CLASS = ConversationWebhookProcessor
    WEBHOOK_PATH = WEBHOOK_PATH

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        if not _INVOKE_AGENT_PORT_MCP_ENABLED:
            return None
        agent_id = run.execution_properties.get("agentId")
        if not isinstance(agent_id, str) or not agent_id:
            return None
        if not bool(run.execution_properties.get("enablePortMcp", True)):
            return None
        return agent_id

    async def execute_foundry(self, run: IntegrationRun) -> None:
        inputs = InvokeAgentInputs.from_execution_properties(run.execution_properties)
        if _INVOKE_AGENT_PORT_MCP_ENABLED and inputs.enablePortMcp:
            try:
                await ensure_port_mcp_on_agent(
                    self.client,
                    self.project_connections,
                    agent_id=inputs.agentId,
                    run=run,
                )
                await remint_port_mcp_for_invoke(
                    self.project_connections,
                    agent_id=inputs.agentId,
                    run=run,
                )
            except ValueError as error:
                raise ActionExecutionError(
                    f"Port MCP setup failed: {error}"
                ) from error
            except RuntimeError as error:
                raise ActionExecutionError(str(error)) from error

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
        stream_key = f"{run.id}:{inputs.agentId}"
        bind_output = {
            "agentId": inputs.agentId,
            "conversationId": conversation_id,
        }

        await self.execute_responses_invoke(
            run,
            invoke_label=f"Invoking Foundry agent {inputs.agentId}",
            stream_key=stream_key,
            invoke_url=invoke_url,
            params=params,
            body=body,
            agent_id=inputs.agentId,
            bind_output=bind_output,
            report_invocation_status=inputs.reportInvocationStatus,
            early_complete_on_bind=not inputs.reportInvocationStatus,
        )
