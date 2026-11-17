from typing import Any

from loguru import logger
from port_ocean.core.handlers.actions.utils import get_run_access_token
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
from azure_integration.foundry.helpers.port_mcp import (
    ensure_ootb_mcp,
    sanitize_git_provider,
)


class InvokeAgentInputs(AbstractFoundryActionInput):
    agentId: str = Field(min_length=1)
    input: str = Field(min_length=1)
    conversationId: str | None = None
    conversationMetadata: dict[str, Any] | None = None
    reportInvocationStatus: bool = Field(default=False)
    enablePortMcp: bool = Field(default=True)
    gitAccessToken: str | None = Field(default=None, min_length=1)
    gitProvider: str = Field(default="github")
    extraBody: dict[str, Any] = Field(default_factory=dict)


class InvokeAgentExecutor(AbstractFoundryExecutor, ResponsesInvokeMixin):
    ACTION_NAME = "invoke_agent"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = InvokeAgentInputs.from_execution_properties(run.execution_properties)
        git_provider = sanitize_git_provider(inputs.gitProvider)
        if inputs.enablePortMcp or inputs.gitAccessToken:
            port_token = get_run_access_token(run) if inputs.enablePortMcp else None
            try:
                await ensure_ootb_mcp(
                    self.client,
                    project_endpoint=inputs.projectEndpoint,
                    agent_id=inputs.agentId,
                    enable_port_mcp=inputs.enablePortMcp,
                    port_access_token=port_token,
                    git_access_token=inputs.gitAccessToken,
                    git_provider=git_provider,
                    attach_to_prompt_agent=True,
                )
            except Exception as error:
                logger.warning(
                    f"Failed to remint ootb MCP on agent {inputs.agentId}: {error}"
                )
        try:
            conversation_id = await resolve_conversation_for_invoke(
                self.client,
                project_endpoint=inputs.projectEndpoint,
                conversation_id=inputs.conversationId,
                metadata=inputs.conversationMetadata,
                agent_id=inputs.agentId,
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to resolve conversation: {error}"
            ) from error
        path, body = build_agent_responses_invoke(
            agent_id=inputs.agentId,
            user_input=inputs.input,
            conversation_id=conversation_id,
            extra_body=inputs.extraBody,
        )
        invoke_url = self.client.build_url(inputs.projectEndpoint, path)
        await self.execute_responses_invoke(
            run,
            invoke_label=f"Invoking Foundry agent {inputs.agentId}",
            stream_key=f"{run.id}:{inputs.agentId}",
            invoke_url=invoke_url,
            body=body,
            bind_output={
                "agentId": inputs.agentId,
                "conversationId": conversation_id,
            },
            report_invocation_status=inputs.reportInvocationStatus,
            early_complete_on_bind=not inputs.reportInvocationStatus,
        )
