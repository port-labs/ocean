from azure_integration.foundry.discovery import (
    parse_cognitive_services_account_arm_id,
)
from azure_integration.foundry.helpers.scope import (
    ArmDeploymentScope,
    account_name_from_project_endpoint,
    clear_arm_scope_cache,
    ensure_arm_deployment_scope,
)
import azure_integration.foundry.helpers.scope as scope_module
import pytest


def test_account_name_from_project_endpoint() -> None:
    endpoint = (
        "https://software-factory.services.ai.azure.com/api/projects/proj-default"
    )
    assert account_name_from_project_endpoint(endpoint) == "software-factory"


def test_parse_cognitive_services_account_arm_id() -> None:
    arm_id = (
        "/subscriptions/sub-1/resourceGroups/rg-1/providers/"
        "Microsoft.CognitiveServices/accounts/software-factory"
    )
    assert parse_cognitive_services_account_arm_id(arm_id) == (
        "sub-1",
        "rg-1",
        "software-factory",
    )


@pytest.mark.asyncio
async def test_ensure_arm_deployment_scope_uses_cache() -> None:
    clear_arm_scope_cache()
    scope_module._scope_by_account["acct"] = ArmDeploymentScope(
        subscription_id="sub-1",
        resource_group_name="rg-1",
        account_name="acct",
        api_version="2025-06-01",
    )
    scope = await ensure_arm_deployment_scope()
    assert scope.account_name == "acct"
    assert scope.subscription_id == "sub-1"
    clear_arm_scope_cache()
