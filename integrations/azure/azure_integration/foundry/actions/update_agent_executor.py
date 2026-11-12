from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryActionInput,
)
from azure_integration.foundry.actions.abstract_executor import FoundryAgentExecutor
from azure_integration.foundry.helpers.agent_api import build_update_agent_body

UPDATING_STATUS_LABEL = "Updating agent"
UPDATE_FAILED_STATUS_LABEL = "Update failed"
AGENT_UPDATED_STATUS_LABEL = "Agent updated"


class UpdateAgentInputs(AbstractFoundryActionInput):
    agentId: str = Field(min_length=1)
    name: str | None = None
    model: str | None = None
    instructions: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class UpdateAgentExecutor(FoundryAgentExecutor):
    ACTION_NAME = "update_agent"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = UpdateAgentInputs.from_execution_properties(run.execution_properties)
        body = build_update_agent_body(
            name=inputs.name,
            model=inputs.model,
            instructions=inputs.instructions,
            config=inputs.config or None,
        )

        if not body:
            raise ActionExecutionError(
                "At least one field must be provided to update",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            )

        await ocean.port_client.post_run_log(
            run,
            f"Updating Foundry agent '{inputs.agentId}'",
            status_label=UPDATING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            agent = await self.client.send_api_request(
                self.client.build_url(
                    inputs.projectEndpoint, f"agents/{inputs.agentId}"
                ),
                method="PATCH",
                json_body=body,
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to update agent: {error}",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            ) from error

        if not isinstance(agent, dict):
            raise ActionExecutionError(
                "Unexpected update agent response",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            )

        logger.info(f"Updated Foundry agent {inputs.agentId} for run {run.id}")
        await self.sync_agent_catalog(
            inputs.agentId, run, project_endpoint=inputs.projectEndpoint
        )
        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Updated agent {inputs.agentId}",
            status_label=AGENT_UPDATED_STATUS_LABEL,
        )
