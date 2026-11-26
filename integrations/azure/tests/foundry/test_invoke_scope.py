from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from azure_integration.foundry.actions.utils import invoke_scope_from_run


def _run(*, output: dict, execution: dict | None = None) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="azure-ai-foundry",
            integrationProvider="azure-ai-foundry",
            integrationInvocationType="invoke_agent",
            integrationActionExecutionProperties=execution or {},
        ),
        output=output,
    )


def test_invoke_scope_prefers_arm_project_id() -> None:
    arm_id = (
        "/subscriptions/s/resourceGroups/rg/providers/"
        "Microsoft.CognitiveServices/accounts/acct/projects/p"
    )
    scope = invoke_scope_from_run(
        _run(
            output={"projectArmId": arm_id},
            execution={
                "agentId": "agent-1",
                "projectEndpoint": "https://x/api/projects/p",
            },
        )
    )
    assert scope is not None
    endpoint, project_id, agent_id = scope
    assert endpoint == "https://acct.services.ai.azure.com/api/projects/p"
    assert project_id == arm_id
    assert agent_id == "agent-1"
