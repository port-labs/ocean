from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from azure_integration.foundry.actions.deploy_model_deployment_executor import (
    DeployModelDeploymentExecutor,
)
from azure_integration.foundry.actions.delete_model_deployment_executor import (
    DeleteModelDeploymentExecutor,
)


def _run(action_type: str, execution_properties: dict[str, object]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="azure",
            integrationProvider="azure",
            integrationInvocationType=action_type,
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.mark.asyncio
async def test_deploy_model_deployment_uses_arm_client() -> None:
    executor = DeployModelDeploymentExecutor()
    executor.arm_deployments = MagicMock()
    executor.arm_deployments.upsert_model_deployment = AsyncMock()
    executor.client = MagicMock()
    executor.client.build_url = MagicMock(
        return_value="https://example/deployments/gpt-5"
    )
    executor.client.send_api_request = AsyncMock(
        return_value={
            "name": "gpt-5",
            "modelName": "gpt-5",
            "type": "ModelDeployment",
            "sku": {"name": "GlobalStandard"},
        }
    )

    run = _run(
        "deploy_model_deployment",
        {
            "projectEndpoint": "https://acct.services.ai.azure.com/api/projects/demo",
            "deploymentName": "gpt-5",
            "modelName": "gpt-5",
            "skuName": "GlobalStandard",
        },
    )

    mock_project = MagicMock(project_arm_id="arm-project-id")
    with (
        patch(
            "azure_integration.foundry.actions.abstract_executor.resolve_project_by_endpoint",
            AsyncMock(return_value=mock_project),
        ),
        patch(
            "azure_integration.foundry.actions.deploy_model_deployment_executor.ocean"
        ) as mock_ocean,
        patch(
            "azure_integration.foundry.helpers.catalog_sync.ocean"
        ) as mock_ocean_base,
    ):
        mock_ocean.port_client.post_run_log = AsyncMock()
        mock_ocean.port_client.report_run_completed = AsyncMock()
        mock_ocean_base.integration.port_app_config_handler.get_port_app_config = (
            AsyncMock()
        )
        mock_ocean_base.register_raw = AsyncMock()
        mock_ocean_base.port_client.post_run_log = AsyncMock()

        await executor.execute(run)

    executor.arm_deployments.upsert_model_deployment.assert_awaited_once()
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(run, True)


@pytest.mark.asyncio
async def test_delete_model_deployment_uses_arm_client() -> None:
    executor = DeleteModelDeploymentExecutor()
    executor.arm_deployments = MagicMock()
    executor.arm_deployments.delete_deployment = AsyncMock()

    run = _run(
        "delete_model_deployment",
        {
            "projectEndpoint": "https://acct.services.ai.azure.com/api/projects/demo",
            "deploymentName": "gpt-5",
        },
    )

    mock_project = MagicMock(project_arm_id="arm-project-id")
    with (
        patch(
            "azure_integration.foundry.actions.abstract_executor.resolve_project_by_endpoint",
            AsyncMock(return_value=mock_project),
        ),
        patch(
            "azure_integration.foundry.actions.delete_model_deployment_executor.ocean"
        ) as mock_ocean,
        patch(
            "azure_integration.foundry.helpers.catalog_sync.ocean"
        ) as mock_ocean_base,
    ):
        mock_ocean.port_client.post_run_log = AsyncMock()
        mock_ocean.port_client.report_run_completed = AsyncMock()
        mock_ocean_base.integration.port_app_config_handler.get_port_app_config = (
            AsyncMock()
        )
        mock_ocean_base.unregister_raw = AsyncMock()
        mock_ocean_base.port_client.post_run_log = AsyncMock()

        await executor.execute(run)

    executor.arm_deployments.delete_deployment.assert_awaited_once_with("gpt-5")
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(run, True)
