from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryActionInput,
)
from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.helpers.utils import enrich_with_project
from azure_integration.foundry.kinds import ObjectKind


class DeleteAgentInputs(AbstractFoundryActionInput):
    agentId: str = Field(min_length=1)


DELETE_FAILED_STATUS_LABEL = "Deletion failed"
AGENT_DELETED_STATUS_LABEL = "Agent deleted"


class DeleteAgentExecutor(AbstractFoundryExecutor):
    ACTION_NAME = "delete_agent"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = DeleteAgentInputs.from_execution_properties(run.execution_properties)
        try:
            await self.client.send_api_request(
                self.client.build_url(
                    inputs.projectEndpoint, f"agents/{inputs.agentId}"
                ),
                method="DELETE",
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to delete agent: {error}",
                status_label=DELETE_FAILED_STATUS_LABEL,
            ) from error

        logger.info(f"Deleted Foundry agent {inputs.agentId} for run {run.id}")
        await self.unregister_entity(
            ObjectKind.FOUNDRY_AGENT,
            enrich_with_project(
                {"id": inputs.agentId, "name": inputs.agentId},
                project_endpoint=inputs.projectEndpoint,
            ),
            run,
        )
        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Deleted agent {inputs.agentId}",
            status_label=AGENT_DELETED_STATUS_LABEL,
        )
