from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from actions.abstract_action_input import AbstractFoundryActionInput
from actions.abstract_executor import AbstractFoundryExecutor
from helpers.agent_api import build_update_agent_body


class UpdateAgentInputs(AbstractFoundryActionInput):
    agentId: str = Field(min_length=1)
    name: str | None = None
    model: str | None = None
    instructions: str | None = None
    metadata: dict[str, Any] | None = None


class UpdateAgentExecutor(AbstractFoundryExecutor):
    ACTION_NAME = "update_agent"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = UpdateAgentInputs.from_execution_properties(run.execution_properties)
        body = build_update_agent_body(
            name=inputs.name,
            model=inputs.model,
            instructions=inputs.instructions,
            metadata=inputs.metadata,
        )

        if not body:
            raise ActionExecutionError("At least one field must be provided to update")

        try:
            agent = await self.client.send_api_request(
                self.client.build_url(
                    self.project_endpoint, f"agents/{inputs.agentId}"
                ),
                method="PATCH",
                json_body=body,
            )
        except Exception as error:
            raise ActionExecutionError(f"Failed to update agent: {error}") from error

        if not isinstance(agent, dict):
            raise ActionExecutionError("Unexpected update agent response")

        logger.info(f"Updated Foundry agent {inputs.agentId} for run {run.id}")
        await self.sync_agent_catalog(inputs.agentId, run)
        await ocean.port_client.report_run_completed(run, True)
