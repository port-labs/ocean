from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryActionInput,
)
from azure_integration.foundry.actions.abstract_executor import ArmDeploymentExecutor
from azure_integration.foundry.kinds import ObjectKind

DEPLOYING_STATUS_LABEL = "Deploying model"
DEPLOY_FAILED_STATUS_LABEL = "Deployment failed"
DEPLOYED_STATUS_LABEL = "Model deployed"


class DeployModelDeploymentInputs(AbstractFoundryActionInput):
    deploymentName: str = Field(min_length=1)
    modelName: str = Field(min_length=1)
    modelVersion: str | None = None
    modelPublisher: str | None = None
    skuName: str = Field(default="GlobalStandard", min_length=1)
    deploymentType: str = Field(default="ModelDeployment", min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class DeployModelDeploymentExecutor(ArmDeploymentExecutor):
    ACTION_NAME = "deploy_model_deployment"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = DeployModelDeploymentInputs.from_execution_properties(
            run.execution_properties
        )

        await ocean.port_client.post_run_log(
            run,
            f"Deploying model '{inputs.modelName}' as '{inputs.deploymentName}' via Azure Resource Manager",
            status_label=DEPLOYING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            await self.arm_deployments.upsert_model_deployment(
                project_endpoint=inputs.projectEndpoint,
                deployment_name=inputs.deploymentName,
                model_name=inputs.modelName,
                model_version=inputs.modelVersion,
                model_publisher=inputs.modelPublisher,
                sku_name=inputs.skuName,
                config=inputs.config or None,
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to deploy model '{inputs.deploymentName}': {error}",
                status_label=DEPLOY_FAILED_STATUS_LABEL,
            ) from error

        deployment: dict[str, Any]
        try:
            payload = await self.client.send_api_request(
                self.client.build_url(
                    inputs.projectEndpoint,
                    f"deployments/{inputs.deploymentName}",
                ),
            )
            deployment = payload if isinstance(payload, dict) and payload else {}
        except Exception:
            deployment = {}

        if not deployment:
            deployment = {
                "name": inputs.deploymentName,
                "type": inputs.deploymentType,
                "modelName": inputs.modelName,
                "modelVersion": inputs.modelVersion,
                "modelPublisher": inputs.modelPublisher,
                "sku": {"name": inputs.skuName},
            }

        logger.info(
            f"Deployed Foundry model deployment {inputs.deploymentName} for run {run.id}"
        )
        await self.register_entity(
            ObjectKind.MODEL_DEPLOYMENT,
            deployment,
            run,
            project_endpoint=inputs.projectEndpoint,
        )
        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Deployed model {inputs.deploymentName}",
            status_label=DEPLOYED_STATUS_LABEL,
        )
