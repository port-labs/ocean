from typing import Any

from loguru import logger
from port_ocean.core.handlers.actions.utils import get_run_access_token
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field, field_validator

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryInvokeInput,
)
from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.actions.responses_invoke_mixin import (
    INVOKE_RUNNING_STATUS_LABEL,
    ResponsesInvokeMixin,
)
from azure_integration.foundry.core.exporters.agents_exporter import AgentsExporter
from azure_integration.foundry.core.options import SingleAgentOptions
from azure_integration.foundry.helpers.conversation_api import (
    resolve_conversation_for_invoke,
)
from azure_integration.foundry.helpers.port_mcp import (
    ensure_port_mcp,
    sanitize_git_provider,
)
from azure_integration.foundry.models.agent import Agent, PromptAgentDefinition


class InvokeAgentInputs(AbstractFoundryInvokeInput):
    agentId: str = Field(min_length=1)
    input: str = Field(min_length=1)
    conversationId: str | None = None
    conversationMetadata: dict[str, Any] | None = None
    reportInvocationStatus: bool = Field(default=False)
    enablePortMcp: bool = Field(default=True)
    gitAccessToken: str | None = Field(default=None, min_length=1)
    gitProvider: str = Field(default="github")
    useExistingToolbox: bool = Field(default=False)
    toolboxName: str | None = Field(default=None, min_length=1)
    extraBody: dict[str, Any] = Field(default_factory=dict)

    @field_validator("gitProvider")
    @classmethod
    def _git_provider(cls, value: str) -> str:
        return sanitize_git_provider(value)

    def build_responses_invoke(
        self, conversation_id: str | None = None
    ) -> tuple[str, dict[str, Any]]:
        path = f"agents/{self.agentId}/endpoint/protocols/openai/responses"
        body: dict[str, Any] = {"input": self.input, **self.extraBody}
        if conversation_id:
            body.setdefault("conversation", conversation_id)
        return path, body


class InvokeAgentExecutor(AbstractFoundryExecutor, ResponsesInvokeMixin):
    ACTION_NAME = "invoke_agent"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        # Serialize same-agent remints of Port/GitHub project connections + toolbox.
        props = run.execution_properties
        agent_id = props.get("agentId")
        if not agent_id:
            return None
        project_arm_id = props.get("projectArmId")
        if (
            isinstance(project_arm_id, str)
            and project_arm_id.strip()
            and "{{" not in project_arm_id
        ):
            return f"{project_arm_id.strip()}:{agent_id}"
        return str(agent_id)

    async def execute(self, run: IntegrationRun) -> None:
        inputs = InvokeAgentInputs.from_execution_properties(run.execution_properties)
        project_endpoint = inputs.project_endpoint
        port_token = get_run_access_token(run) if inputs.enablePortMcp else None
        # Remint only when credentials exist; bare enablePortMcp without a token
        # must not strip existing toolboxes or fail hosted invokes.
        want_mcp = bool(inputs.gitAccessToken) or (
            inputs.enablePortMcp and bool(port_token)
        )
        if inputs.enablePortMcp and not port_token:
            logger.warning(
                f"enablePortMcp set for invoke on agent {inputs.agentId} but "
                "no execution identity token; Port connection will not be reminted"
            )
        if want_mcp:
            await self._ensure_mcp_before_invoke(
                inputs, port_token, project_endpoint, run
            )
        try:
            conversation_id = await resolve_conversation_for_invoke(
                self.client,
                project_endpoint=project_endpoint,
                conversation_id=inputs.conversationId,
                metadata=inputs.conversationMetadata,
                agent_id=inputs.agentId,
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to resolve conversation: {error}"
            ) from error
        path, body = inputs.build_responses_invoke(conversation_id)
        invoke_url = self.client.build_url(project_endpoint, path)
        bind_output: dict[str, Any] = {
            "conversationId": conversation_id,
            "projectArmId": inputs.projectArmId,
        }
        await self.execute_responses_invoke(
            run,
            invoke_label=f"Invoking Foundry agent {inputs.agentId}",
            stream_key=f"{run.id}:{inputs.agentId}",
            invoke_url=invoke_url,
            body=body,
            bind_output=bind_output,
            report_invocation_status=inputs.reportInvocationStatus,
            early_complete_on_bind=not inputs.reportInvocationStatus,
            running_status_label=INVOKE_RUNNING_STATUS_LABEL,
        )

    async def _ensure_mcp_before_invoke(
        self,
        inputs: InvokeAgentInputs,
        port_token: str | None,
        project_endpoint: str,
        run: IntegrationRun,
    ) -> None:
        try:
            agent_payload = await AgentsExporter(self.client).get_resource(
                SingleAgentOptions(
                    project_endpoint=project_endpoint,
                    project_id=inputs.projectArmId,
                    agent_id=inputs.agentId,
                )
            )
        except Exception as error:
            # Kind unknown without the agent payload — do not guess prompt vs hosted.
            raise ActionExecutionError(
                f"Could not load agent {inputs.agentId} before MCP remint: {error}"
            ) from error
        if agent_payload is None:
            raise ActionExecutionError(
                f"Could not load agent {inputs.agentId} before MCP remint: not found"
            )

        agent = Agent.model_validate(agent_payload)
        hosted = agent.kind == "hosted"
        definition = agent.latest_version.definition
        tools = (
            definition.tools
            if isinstance(definition, PromptAgentDefinition)
            else []
        )
        # Prompt uses useExistingToolbox only; hosted uses toolboxName only.
        try:
            toolbox_result = await ensure_port_mcp(
                self.client,
                project_endpoint=project_endpoint,
                agent_id=inputs.agentId,
                enable_port_mcp=inputs.enablePortMcp,
                port_access_token=port_token,
                git_access_token=inputs.gitAccessToken,
                existing_agent=agent_payload,
                existing_tools=tools,
                toolbox_name=inputs.toolboxName if hosted else None,
                use_existing_toolbox=(
                    inputs.useExistingToolbox if not hosted else False
                ),
                agent_kind=agent.kind,
                project_arm_id=inputs.projectArmId,
                run=run,
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to prepare toolbox for agent {inputs.agentId}: {error}"
            ) from error

        if hosted and toolbox_result is None:
            raise ActionExecutionError(
                f"Hosted agent {inputs.agentId} has no toolbox ready for invoke. "
                "Pass enablePortMcp with an execution identity and/or gitAccessToken. "
                "Optionally pass toolboxName for an existing Foundry toolbox "
                "(must already exist; consent to edit)."
            )
