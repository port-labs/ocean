from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from actions.abstract_action_input import AbstractFoundryActionInput
from actions.abstract_executor import AbstractFoundryExecutor
from integration import ObjectKind


class DeleteModelDeploymentInputs(AbstractFoundryActionInput):
    deploymentName: str = Field(min_length=1)


class DeleteModelDeploymentExecutor(AbstractFoundryExecutor):
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
            await self.arm_deployments.delete_deployment(inputs.deploymentName)
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to delete deployment '{inputs.deploymentName}': {error}"
            ) from error

        logger.info(
            f"Deleted Foundry deployment {inputs.deploymentName} for run {run.id}"
        )
        await self.unregister_by_identifier(
            ObjectKind.MODEL_DEPLOYMENT, inputs.deploymentName, run
        )
        await ocean.port_client.report_run_completed(run, True)
