from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from azure_integration.foundry.actions.deploy_model_deployment_executor import (
    DeployModelDeploymentExecutor,
    deployment_from_arm,
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


def test_deployment_from_arm_maps_catalog_shape() -> None:
    deployment = deployment_from_arm(
        {
            "name": "gpt-5",
            "sku": {"name": "GlobalStandard", "capacity": 1},
            "properties": {
                "model": {
                    "format": "OpenAI",
                    "name": "gpt-5",
                    "version": "2025-01-01",
                }
            },
        },
        deployment_name="fallback",
        model_name="fallback-model",
        model_version=None,
        model_publisher=None,
        sku_name="GlobalStandard",
    )
    assert deployment == {
        "name": "gpt-5",
        "type": "ModelDeployment",
        "modelName": "gpt-5",
        "modelVersion": "2025-01-01",
        "modelPublisher": "OpenAI",
        "sku": {"name": "GlobalStandard", "capacity": 1},
    }


@pytest.mark.asyncio
async def test_deploy_model_deployment_uses_arm_client() -> None:
    executor = DeployModelDeploymentExecutor()
    executor.foundry_arm = MagicMock()
    executor.foundry_arm.upsert_model_deployment = AsyncMock(
        return_value={
            "name": "gpt-5",
            "sku": {"name": "GlobalStandard"},
            "properties": {"model": {"format": "OpenAI", "name": "gpt-5"}},
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

    with (
        patch(
            "azure_integration.foundry.actions.deploy_model_deployment_executor.ocean"
        ) as mock_ocean,
        patch(
            "azure_integration.foundry.actions.abstract_executor.ocean"
        ) as mock_ocean_base,
    ):
        mock_ocean.port_client.post_run_log = AsyncMock()
        mock_ocean.port_client.report_run_completed = AsyncMock()
        mock_ocean_base.register_raw = AsyncMock()
        mock_ocean_base.port_client.post_run_log = AsyncMock()

        await executor.execute(run)

    executor.foundry_arm.upsert_model_deployment.assert_awaited_once()
    mock_ocean_base.register_raw.assert_awaited_once()
    registered = mock_ocean_base.register_raw.await_args.args[1][0]
    assert registered["name"] == "gpt-5"
    assert registered["type"] == "ModelDeployment"
    assert registered["__foundryProjectName"] == "demo"
    mock_ocean.port_client.report_run_completed.assert_awaited_once()
    assert mock_ocean.port_client.report_run_completed.await_args.args[:2] == (
        run,
        True,
    )


@pytest.mark.asyncio
async def test_delete_model_deployment_uses_arm_client() -> None:
    executor = DeleteModelDeploymentExecutor()
    executor.foundry_arm = MagicMock()
    executor.foundry_arm.delete_deployment = AsyncMock()

    run = _run(
        "delete_model_deployment",
        {
            "projectEndpoint": "https://acct.services.ai.azure.com/api/projects/demo",
            "deploymentName": "gpt-5",
        },
    )

    with (
        patch(
            "azure_integration.foundry.actions.delete_model_deployment_executor.ocean"
        ) as mock_ocean,
        patch(
            "azure_integration.foundry.actions.abstract_executor.ocean"
        ) as mock_ocean_base,
    ):
        mock_ocean.port_client.post_run_log = AsyncMock()
        mock_ocean.port_client.report_run_completed = AsyncMock()
        mock_ocean_base.unregister_raw = AsyncMock()
        mock_ocean_base.port_client.post_run_log = AsyncMock()

        await executor.execute(run)

    executor.foundry_arm.delete_deployment.assert_awaited_once_with(
        "https://acct.services.ai.azure.com/api/projects/demo",
        "gpt-5",
    )
    mock_ocean.port_client.report_run_completed.assert_awaited_once()
    assert mock_ocean.port_client.report_run_completed.await_args.args[:2] == (
        run,
        True,
    )
