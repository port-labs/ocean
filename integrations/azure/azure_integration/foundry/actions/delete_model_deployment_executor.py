from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryActionInput,
)
from azure_integration.foundry.actions.abstract_executor import ArmDeploymentExecutor
from azure_integration.foundry.helpers.utils import enrich_with_project
from azure_integration.foundry.kinds import ObjectKind


class DeleteModelDeploymentInputs(AbstractFoundryActionInput):
    deploymentName: str = Field(min_length=1)


DELETE_FAILED_STATUS_LABEL = "Deletion failed"
DEPLOYMENT_DELETED_STATUS_LABEL = "Deployment deleted"


class DeleteModelDeploymentExecutor(ArmDeploymentExecutor):
    ACTION_NAME = "delete_model_deployment"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = DeleteModelDeploymentInputs.from_execution_properties(
            run.execution_properties
        )
        await ocean.port_client.post_run_log(
            run,
            f"Deleting deployment '{inputs.deploymentName}' in Azure (Resource Manager)",
            should_raise=False,
        )
        try:
            await self.arm_deployments.delete_deployment(
                inputs.projectEndpoint, inputs.deploymentName
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to delete deployment '{inputs.deploymentName}': {error}",
                status_label=DELETE_FAILED_STATUS_LABEL,
            ) from error

        logger.info(
            f"Deleted Foundry deployment {inputs.deploymentName} for run {run.id}"
        )
        await self.unregister_entity(
            ObjectKind.FOUNDRY_MODEL_DEPLOYMENT,
            enrich_with_project(
                {
                    "id": inputs.deploymentName,
                    "name": inputs.deploymentName,
                },
                project_endpoint=inputs.projectEndpoint,
            ),
            run,
        )
        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Deleted deployment {inputs.deploymentName}",
            status_label=DEPLOYMENT_DELETED_STATUS_LABEL,
        )
