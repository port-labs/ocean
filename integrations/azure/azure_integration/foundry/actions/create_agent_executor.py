from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from azure_integration.foundry.actions.abstract_action_input import AbstractFoundryActionInput
from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.helpers.port_mcp import ensure_port_mcp_on_agent
from azure_integration.foundry.helpers.agent_api import build_create_agent_body


class CreateAgentInputs(AbstractFoundryActionInput):
    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    instructions: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    enablePortMcp: bool = Field(default=True)


class CreateAgentExecutor(AbstractFoundryExecutor):
    ACTION_NAME = "create_agent"

    async def execute_foundry(self, run: IntegrationRun) -> None:
        inputs = CreateAgentInputs.from_execution_properties(run.execution_properties)
        body = build_create_agent_body(
            name=inputs.name,
            model=inputs.model,
            instructions=inputs.instructions,
            metadata=inputs.metadata or None,
        )

        await ocean.port_client.post_run_log(
            run,
            f"Creating Foundry agent '{inputs.name}'",
            should_raise=False,
        )

        try:
            agent = await self.client.send_api_request(
                self.client.build_url(self.project_endpoint, "agents"),
                method="POST",
                json_body=body,
            )
        except Exception as error:
            raise ActionExecutionError(f"Failed to create agent: {error}") from error

        if not isinstance(agent, dict):
            raise ActionExecutionError("Unexpected create agent response")

        logger.info(f"Created Foundry agent {agent.get('id')} for run {run.id}")
        agent_id = str(agent.get("id") or agent.get("name") or inputs.name)
        if inputs.enablePortMcp:
            await ensure_port_mcp_on_agent(
                self.client,
                self.project_connections,
                agent_id=agent_id,
                run=run,
            )
        await self.sync_agent_catalog(agent_id, run)

        if isinstance(run, WorkflowNodeRun):
            run.output["agentId"] = agent_id

        await ocean.port_client.report_run_completed(run, True)
