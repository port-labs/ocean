from unittest.mock import MagicMock, patch

import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from azure_integration.foundry.actions.invoke_agent_executor import InvokeAgentExecutor


def _run(execution_properties: dict[str, object]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="azure",
            integrationProvider="azure",
            integrationInvocationType="invoke_agent",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.mark.asyncio
async def test_partition_key_uses_project_and_agent() -> None:
    with patch(
        "azure_integration.foundry.actions.abstract_executor.create_foundry_client",
        return_value=MagicMock(),
    ):
        executor = InvokeAgentExecutor()
    arm_id = (
        "/subscriptions/s/resourceGroups/rg/providers/"
        "Microsoft.CognitiveServices/accounts/acct/projects/p1"
    )
    run = _run({"projectArmId": arm_id, "agentId": "agent-1"})
    assert await executor._get_partition_key(run) == f"{arm_id}:agent-1"


@pytest.mark.asyncio
async def test_partition_key_falls_back_to_agent_id() -> None:
    with patch(
        "azure_integration.foundry.actions.abstract_executor.create_foundry_client",
        return_value=MagicMock(),
    ):
        executor = InvokeAgentExecutor()
    assert await executor._get_partition_key(_run({"agentId": "agent-1"})) == "agent-1"
    assert await executor._get_partition_key(_run({})) is None
