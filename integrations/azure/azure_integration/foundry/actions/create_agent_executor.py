from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.utils import get_run_access_token
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryActionInput,
)
from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.helpers.agent_api import (
    definition_kind,
    foundry_features_header,
)
from azure_integration.foundry.helpers.port_mcp import (
    ensure_ootb_mcp,
    sanitize_git_provider,
)
from azure_integration.foundry.helpers.utils import deep_merge, enrich_with_project
from azure_integration.foundry.kinds import ObjectKind

CREATING_STATUS_LABEL = "Creating agent"
CREATE_FAILED_STATUS_LABEL = "Creation failed"
AGENT_CREATED_STATUS_LABEL = "Agent created"


class CreateAgentInputs(AbstractFoundryActionInput):
    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    instructions: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    enablePortMcp: bool = Field(default=True)
    gitAccessToken: str | None = Field(default=None, min_length=1)
    gitProvider: str = Field(default="github")
    toolboxName: str | None = Field(default=None, min_length=1)

    def to_api_body(self) -> dict[str, Any]:
        # First-class fields win; config deep-merged underneath for passthrough API fields.
        body = deep_merge({"definition": {"kind": "prompt"}}, self.config)
        definition = body.get("definition")
        if not isinstance(definition, dict):
            definition = {}
            body["definition"] = definition

        body["name"] = self.name
        definition["kind"] = definition.get("kind") or "prompt"
        if definition["kind"] == "prompt":
            definition["model"] = self.model
            if self.instructions is not None:
                definition["instructions"] = self.instructions
        return body


class CreateAgentExecutor(AbstractFoundryExecutor):
    ACTION_NAME = "create_agent"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CreateAgentInputs.from_execution_properties(run.execution_properties)
        git_provider = sanitize_git_provider(inputs.gitProvider)
        port_token = get_run_access_token(run) if inputs.enablePortMcp else None
        body = inputs.to_api_body()

        await ocean.port_client.post_run_log(
            run,
            f"Creating Foundry agent '{inputs.name}' with model {inputs.model}",
            status_label=CREATING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            agent = await self.client.send_api_request(
                self.client.build_url(inputs.projectEndpoint, "agents"),
                method="POST",
                json_body=body,
                extra_headers=foundry_features_header(definition_kind(body)),
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to create agent: {error}",
                status_label=CREATE_FAILED_STATUS_LABEL,
            ) from error

        if not isinstance(agent, dict):
            raise ActionExecutionError(
                "Unexpected create agent response",
                status_label=CREATE_FAILED_STATUS_LABEL,
            )

        agent_id = str(agent.get("id") or agent.get("name") or inputs.name)

        toolbox_name: str | None = None
        if inputs.enablePortMcp or inputs.gitAccessToken:
            try:
                toolbox_result = await ensure_ootb_mcp(
                    self.client,
                    project_endpoint=inputs.projectEndpoint,
                    agent_id=agent_id,
                    enable_port_mcp=inputs.enablePortMcp,
                    port_access_token=port_token,
                    git_access_token=inputs.gitAccessToken,
                    git_provider=git_provider,
                    attach_to_prompt_agent=True,
                    toolbox_name=inputs.toolboxName,
                    agent_kind=definition_kind(body),
                )
            except Exception as error:
                raise ActionExecutionError(
                    f"Failed to prepare ootb MCP toolbox: {error}",
                    status_label=CREATE_FAILED_STATUS_LABEL,
                ) from error
            if toolbox_result:
                toolbox_name, _ = toolbox_result

        logger.info(f"Created Foundry agent {agent.get('id')} for run {run.id}")
        await self.register_entity(
            ObjectKind.FOUNDRY_AGENT,
            enrich_with_project(agent, project_endpoint=inputs.projectEndpoint),
            run,
        )

        if isinstance(run, WorkflowNodeRun):
            run.output["agentId"] = agent_id
            if toolbox_name:
                run.output["toolboxName"] = toolbox_name

        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Created agent {agent_id}",
            status_label=AGENT_CREATED_STATUS_LABEL,
        )
