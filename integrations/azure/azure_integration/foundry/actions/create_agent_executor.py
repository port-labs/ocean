from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryActionInput,
)
from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.helpers.utils import deep_merge, enrich_with_project
from azure_integration.foundry.kinds import ObjectKind
from azure_integration.foundry.models.agent import parse_agent_definition

CREATING_STATUS_LABEL = "Creating agent"
CREATE_FAILED_STATUS_LABEL = "Creation failed"
AGENT_CREATED_STATUS_LABEL = "Agent created"


class CreateAgentInputs(AbstractFoundryActionInput):
    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    instructions: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)

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
                extra_headers=parse_agent_definition(
                    body["definition"]
                ).features_header,
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

        logger.info(f"Created Foundry agent {agent.get('id')} for run {run.id}")
        await self.register_entity(
            ObjectKind.FOUNDRY_AGENT,
            enrich_with_project(agent, project_endpoint=inputs.projectEndpoint),
            run,
        )

        if isinstance(run, WorkflowNodeRun):
            run.output["agentId"] = agent_id

        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Created agent {agent_id}",
            status_label=AGENT_CREATED_STATUS_LABEL,
        )
