import pytest

import helpers.arm_scope as arm_scope_module
from helpers.arm_scope import (
    ArmDeploymentScope,
    account_name_from_project_endpoint,
    clear_arm_scope_cache,
    get_arm_deployment_scope,
    parse_cognitive_services_account_arm_id,
    _account_matches_endpoint_key,
    _pick_account_matches,
    _scope_from_integration_config,
)


def test_account_name_from_project_endpoint() -> None:
    endpoint = "https://software-factory.services.ai.azure.com/api/projects/proj-default"
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


def test_pick_account_matches_custom_subdomain() -> None:
    accounts = [
        {
            "name": "other",
            "properties": {"customSubDomainName": "software-factory"},
            "id": "/subscriptions/s/rg/x/providers/Microsoft.CognitiveServices/accounts/other",
        }
    ]
    matches = _pick_account_matches(accounts, "software-factory")
    assert len(matches) == 1
    assert _account_matches_endpoint_key(matches[0], "software-factory")


def test_get_arm_deployment_scope_uses_cache() -> None:
    clear_arm_scope_cache()
    arm_scope_module._resolved_scope = ArmDeploymentScope(
        subscription_id="sub-1",
        resource_group_name="rg-1",
        account_name="software-factory",
        api_version="2025-06-01",
    )
    scope = get_arm_deployment_scope()
    assert scope.subscription_id == "sub-1"
    assert scope.resource_group_name == "rg-1"
    clear_arm_scope_cache()


def test_get_arm_deployment_scope_requires_resolve_when_missing() -> None:
    clear_arm_scope_cache()
    with pytest.raises(ValueError, match="not been resolved"):
        get_arm_deployment_scope()


def test_scope_from_integration_config_uses_endpoint_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "helpers.arm_scope.get_project_endpoint",
        lambda: "https://software-factory.services.ai.azure.com/api/projects/proj-default",
    )
    scope = _scope_from_integration_config(
        {
            "azureSubscriptionId": "sub-1",
            "azureResourceGroupName": "rg-1",
        }
    )
    assert scope is not None
    assert scope.subscription_id == "sub-1"
    assert scope.resource_group_name == "rg-1"
    assert scope.account_name == "software-factory"


def test_scope_from_integration_config_requires_both_fields() -> None:
    with pytest.raises(ValueError, match="Both azureSubscriptionId"):
        _scope_from_integration_config({"azureSubscriptionId": "sub-1"})
