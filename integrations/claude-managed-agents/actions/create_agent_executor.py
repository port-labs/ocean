from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from actions.abstract_action_input import AbstractAnthropicActionInput
from actions.abstract_executor import AbstractAnthropicExecutor
from actions.port_mcp_utils import attach_port_mcp_settings_to_agent_config
from integration import ObjectKind

CREATING_STATUS_LABEL = "Creating agent"
CREATE_FAILED_STATUS_LABEL = "Creation failed"
AGENT_CREATED_STATUS_LABEL = "Agent created"


class CreateAgentInputs(AbstractAnthropicActionInput):
    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    systemPrompt: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    enablePortMcp: bool = True


class CreateAgentExecutor(AbstractAnthropicExecutor):
    """Executor for the `create_agent` action.

    Creates a Claude managed agent, reflects it into the catalog (if the `agent`
    kind is mapped), and completes the run synchronously - there is no async
    webhook for agent creation.
    """

    ACTION_NAME = "create_agent"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CreateAgentInputs.from_execution_properties(run.execution_properties)
        extra = inputs.config
        if inputs.enablePortMcp:
            extra = attach_port_mcp_settings_to_agent_config(inputs.config)

        await ocean.port_client.post_run_log(
            run,
            f"Creating Claude agent '{inputs.name}' with model {inputs.model}",
            status_label=CREATING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            agent = await self.client.create_agent(
                name=inputs.name,
                model=inputs.model,
                system=inputs.systemPrompt,
                extra=extra,
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to create agent: {error}",
                status_label=CREATE_FAILED_STATUS_LABEL,
            ) from error

        logger.info(f"Created Claude agent {agent.id} for run {run.id}")

        # Reflect the new agent in the catalog immediately via the `agent` kind
        # mapping (webhooks also keep agents in sync). Best-effort: never fails
        # the run.
        await self.register_entity(
            ObjectKind.AGENT, agent.to_dict(mode="json", warnings=False), run
        )

        if isinstance(run, WorkflowNodeRun):
            # Expose the created agent's id as a workflow output so later nodes
            # (e.g. `trigger_agent`) can reference it. Classic self-service action
            # runs have no structured output field, so this only applies here.
            run.output["agentId"] = agent.id

        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Created agent {agent.id}",
            status_label=AGENT_CREATED_STATUS_LABEL,
        )
