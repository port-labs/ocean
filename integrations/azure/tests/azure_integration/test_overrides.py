import pytest
from azure_integration.overrides import (
    AzurePortAppConfig,
    AzureResourceGroupResourceConfig,
    AzureSubscriptionResourceConfig,
    AzureCloudResourceConfig,
    AzureCustomKindResourceConfig,
)

SUBSCRIPTION_PORT_MAPPING = {
    "entity": {
        "mappings": {
            "identifier": ".id",
            "title": ".display_name",
            "blueprint": '"azureSubscription"',
            "properties": {
                "tags": ".tags",
            },
        }
    }
}

RESOURCE_GROUP_PORT_MAPPING = {
    "entity": {
        "mappings": {
            "identifier": '.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | join("/")',
            "title": ".name",
            "blueprint": '"azureResourceGroup"',
            "properties": {
                "location": ".location",
                "provisioningState": ".properties.provisioningState + .properties.provisioning_state",
                "tags": ".tags",
            },
            "relations": {
                "subscription": '.id | split("/") | .[1] |= ascii_downcase |.[2] |= ascii_downcase | .[:3] |join("/")',
            },
        }
    }
}

CLOUD_RESOURCE_PORT_MAPPING = {
    "entity": {
        "mappings": {
            "identifier": '.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | join("/")',
            "title": ".name",
            "blueprint": '"azureCloudResource"',
            "properties": {
                "location": ".location",
                "type": ".type",
                "tags": ".tags",
            },
            "relations": {
                "resource_group": '.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | .[:5] |join("/")',
            },
        }
    }
}


def test_azure_subscription_resource_config_parses_correctly() -> None:
    config = AzurePortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "subscription",
                    "selector": {"query": "true", "apiVersion": "2022-09-01"},
                    "port": SUBSCRIPTION_PORT_MAPPING,
                }
            ]
        }
    )
    assert len(config.resources) == 1
    assert isinstance(config.resources[0], AzureSubscriptionResourceConfig)
    assert config.resources[0].kind == "subscription"
    assert config.resources[0].selector.api_version == "2022-09-01"


def test_azure_resource_group_resource_config_parses_correctly() -> None:
    config = AzurePortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "Microsoft.Resources/resourceGroups",
                    "selector": {"query": "true", "apiVersion": "2022-09-01"},
                    "port": RESOURCE_GROUP_PORT_MAPPING,
                }
            ]
        }
    )
    assert len(config.resources) == 1
    assert isinstance(config.resources[0], AzureResourceGroupResourceConfig)
    assert config.resources[0].kind == "Microsoft.Resources/resourceGroups"
    assert config.resources[0].selector.api_version == "2022-09-01"


def test_azure_cloud_resource_config_parses_correctly() -> None:
    config = AzurePortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "cloudResource",
                    "selector": {
                        "query": "true",
                        "resourceKinds": {
                            "Microsoft.Storage/storageAccounts": "2023-01-01",
                            "Microsoft.Compute/virtualMachines": "2023-03-01",
                        },
                    },
                    "port": CLOUD_RESOURCE_PORT_MAPPING,
                }
            ]
        }
    )
    assert len(config.resources) == 1
    assert isinstance(config.resources[0], AzureCloudResourceConfig)
    assert config.resources[0].kind == "cloudResource"
    assert (
        "Microsoft.Storage/storageAccounts"
        in config.resources[0].selector.resource_kinds
    )


def test_azure_cloud_resource_config_rejects_empty_resource_kinds() -> None:
    with pytest.raises(Exception):
        AzurePortAppConfig.parse_obj(
            {
                "resources": [
                    {
                        "kind": "cloudResource",
                        "selector": {"query": "true", "resourceKinds": {}},
                        "port": CLOUD_RESOURCE_PORT_MAPPING,
                    }
                ]
            }
        )


def test_azure_custom_kind_storage_account_parses_correctly() -> None:
    config = AzurePortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "Microsoft.Storage/storageAccounts",
                    "selector": {"query": "true", "apiVersion": "2023-01-01"},
                    "port": CLOUD_RESOURCE_PORT_MAPPING,
                }
            ]
        }
    )
    assert len(config.resources) == 1
    assert isinstance(config.resources[0], AzureCustomKindResourceConfig)
    assert config.resources[0].kind == "Microsoft.Storage/storageAccounts"
    assert config.resources[0].selector.api_version == "2023-01-01"


def test_azure_custom_kind_virtual_machine_parses_correctly() -> None:
    config = AzurePortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "Microsoft.Compute/virtualMachines",
                    "selector": {"query": "true", "apiVersion": "2023-03-01"},
                    "port": CLOUD_RESOURCE_PORT_MAPPING,
                }
            ]
        }
    )
    assert len(config.resources) == 1
    assert isinstance(config.resources[0], AzureCustomKindResourceConfig)
    assert config.resources[0].kind == "Microsoft.Compute/virtualMachines"


def test_azure_port_app_config_allow_custom_kinds_is_enabled() -> None:
    assert AzurePortAppConfig.allow_custom_kinds is True


def test_azure_port_app_config_parses_full_real_world_mapping() -> None:
    config = AzurePortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "subscription",
                    "selector": {"query": "true", "apiVersion": "2022-09-01"},
                    "port": SUBSCRIPTION_PORT_MAPPING,
                },
                {
                    "kind": "Microsoft.Resources/resourceGroups",
                    "selector": {"query": "true", "apiVersion": "2022-09-01"},
                    "port": RESOURCE_GROUP_PORT_MAPPING,
                },
                {
                    "kind": "Microsoft.Storage/storageAccounts",
                    "selector": {"query": "true", "apiVersion": "2023-01-01"},
                    "port": CLOUD_RESOURCE_PORT_MAPPING,
                },
                {
                    "kind": "Microsoft.Compute/virtualMachines",
                    "selector": {"query": "true", "apiVersion": "2023-03-01"},
                    "port": CLOUD_RESOURCE_PORT_MAPPING,
                },
                {
                    "kind": "Microsoft.ContainerService/managedClusters",
                    "selector": {"query": "true", "apiVersion": "2023-05-01"},
                    "port": CLOUD_RESOURCE_PORT_MAPPING,
                },
            ]
        }
    )
    assert len(config.resources) == 5
    assert isinstance(config.resources[0], AzureSubscriptionResourceConfig)
    assert isinstance(config.resources[1], AzureResourceGroupResourceConfig)
    assert isinstance(config.resources[2], AzureCustomKindResourceConfig)
    assert isinstance(config.resources[3], AzureCustomKindResourceConfig)
    assert isinstance(config.resources[4], AzureCustomKindResourceConfig)
