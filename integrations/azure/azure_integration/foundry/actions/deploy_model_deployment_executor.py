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
from azure_integration.foundry.helpers.utils import enrich_with_project
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
    config: dict[str, Any] = Field(default_factory=dict)


def deployment_from_arm(
    arm_payload: dict[str, Any],
    *,
    deployment_name: str,
    model_name: str,
    model_version: str | None,
    model_publisher: str | None,
    sku_name: str,
) -> dict[str, Any]:
    """Map ARM deployment PUT response into data-plane catalog shape."""
    props = arm_payload.get("properties")
    model = props.get("model") if isinstance(props, dict) else None
    if not isinstance(model, dict):
        model = {}
    sku = arm_payload.get("sku")
    return {
        "name": arm_payload.get("name") or deployment_name,
        "type": "ModelDeployment",
        "modelName": model.get("name") or model_name,
        "modelVersion": model.get("version") or model_version,
        "modelPublisher": model.get("format") or model_publisher,
        "sku": sku if isinstance(sku, dict) else {"name": sku_name},
    }


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
            arm_payload = await self.arm_deployments.upsert_model_deployment(
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

        deployment = deployment_from_arm(
            arm_payload if isinstance(arm_payload, dict) else {},
            deployment_name=inputs.deploymentName,
            model_name=inputs.modelName,
            model_version=inputs.modelVersion,
            model_publisher=inputs.modelPublisher,
            sku_name=inputs.skuName,
        )

        logger.info(
            f"Deployed Foundry model deployment {inputs.deploymentName} for run {run.id}"
        )
        await self.register_entity(
            ObjectKind.FOUNDRY_MODEL_DEPLOYMENT,
            enrich_with_project(deployment, project_endpoint=inputs.projectEndpoint),
            run,
        )
        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Deployed model {inputs.deploymentName}",
            status_label=DEPLOYED_STATUS_LABEL,
        )
