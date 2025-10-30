"""Tests for Azure integration utility functions"""

from azure_integration.utils import (
    ResourceKindsWithSpecialHandling,
    resolve_resource_type_from_resource_uri,
    is_sub_resource,
    get_resource_kind_by_level,
    get_resource_configs_with_resource_kind,
)
from azure_integration.overrides import (
    AzureSpecificKindsResourceConfig,
    AzureCloudResourceConfig,
    AzureSpecificKindSelector,
    AzureCloudResourceSelector,
)
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)


class TestResolveResourceTypeFromResourceUri:
    """Test resolve_resource_type_from_resource_uri function"""

    def test_resolves_resource_group(self) -> None:
        """Test resolving resource group from URI"""
        uri = "/subscriptions/test-sub/resourceGroups/test-rg"
        result = resolve_resource_type_from_resource_uri(uri)
        assert result == ResourceKindsWithSpecialHandling.RESOURCE_GROUPS

    def test_resolves_base_resource(self) -> None:
        """Test resolving base resource type from URI"""
        uri = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage"
        result = resolve_resource_type_from_resource_uri(uri)
        assert result == "Microsoft.Storage/storageAccounts"

    def test_resolves_extension_resource(self) -> None:
        """Test resolving extension resource type from URI"""
        uri = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ServiceBus/namespaces/test-ns/queues/test-queue"
        result = resolve_resource_type_from_resource_uri(uri)
        assert result == "Microsoft.ServiceBus/namespaces/queues"

    def test_resolves_nested_extension_resource(self) -> None:
        """Test resolving deeply nested extension resource type from URI"""
        uri = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ServiceBus/namespaces/test-ns/topics/test-topic/subscriptions/test-sub"
        result = resolve_resource_type_from_resource_uri(uri)
        assert result == "Microsoft.ServiceBus/namespaces/topics/subscriptions"


class TestIsSubResource:
    """Test is_sub_resource function"""

    def test_base_resource_is_not_sub_resource(self) -> None:
        """Test that base resources are not sub resources"""
        assert is_sub_resource("Microsoft.Storage/storageAccounts") is False
        assert is_sub_resource("Microsoft.Compute/virtualMachines") is False

    def test_extension_resource_is_sub_resource(self) -> None:
        """Test that extension resources are sub resources"""
        assert is_sub_resource("Microsoft.ServiceBus/namespaces/queues") is True
        assert is_sub_resource("Microsoft.ServiceBus/namespaces/topics") is True

    def test_nested_extension_resource_is_sub_resource(self) -> None:
        """Test that nested extension resources are sub resources"""
        assert (
            is_sub_resource("Microsoft.ServiceBus/namespaces/topics/subscriptions")
            is True
        )


class TestGetResourceKindByLevel:
    """Test get_resource_kind_by_level function"""

    def test_level_0_returns_base_resource(self) -> None:
        """Test getting base resource at level 0"""
        resource_kind = "Microsoft.Storage/storageAccounts/blobServices/containers"
        result, is_last = get_resource_kind_by_level(resource_kind, level=0)
        assert result == "Microsoft.Storage/storageAccounts"
        assert is_last is False

    def test_level_1_returns_first_extension(self) -> None:
        """Test getting first extension at level 1"""
        resource_kind = "Microsoft.Storage/storageAccounts/blobServices/containers"
        result, is_last = get_resource_kind_by_level(resource_kind, level=1)
        assert result == "Microsoft.Storage/storageAccounts/blobServices"
        assert is_last is False

    def test_level_2_returns_second_extension(self) -> None:
        """Test getting second extension at level 2"""
        resource_kind = "Microsoft.Storage/storageAccounts/blobServices/containers"
        result, is_last = get_resource_kind_by_level(resource_kind, level=2)
        assert result == "Microsoft.Storage/storageAccounts/blobServices/containers"
        assert is_last is True

    def test_base_resource_only(self) -> None:
        """Test with base resource only"""
        resource_kind = "Microsoft.Compute/virtualMachines"
        result, is_last = get_resource_kind_by_level(resource_kind, level=0)
        assert result == "Microsoft.Compute/virtualMachines"
        assert is_last is True


class TestGetResourceConfigsWithResourceKind:
    """Test get_resource_configs_with_resource_kind function"""

    def test_finds_matching_specific_kind(self) -> None:
        """Test finding resource config with specific kind"""
        config = AzureSpecificKindsResourceConfig(
            kind="Microsoft.Storage/storageAccounts",
            selector=AzureSpecificKindSelector(query="true", apiVersion="2023-01-01"),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )

        result = get_resource_configs_with_resource_kind(
            resource_kind="Microsoft.Storage/storageAccounts",
            resource_configs=[config],
        )

        assert len(result) == 1
        assert result[0].kind == "Microsoft.Storage/storageAccounts"

    def test_does_not_find_non_matching_kind(self) -> None:
        """Test that non-matching kinds are not returned"""
        config = AzureSpecificKindsResourceConfig(
            kind="Microsoft.Compute/virtualMachines",
            selector=AzureSpecificKindSelector(query="true", apiVersion="2023-03-01"),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )

        result = get_resource_configs_with_resource_kind(
            resource_kind="Microsoft.Storage/storageAccounts",
            resource_configs=[config],
        )

        assert len(result) == 0

    def test_finds_cloud_resource_kind(self) -> None:
        """Test finding resource config with cloud resource selector"""
        config = AzureCloudResourceConfig(
            kind="cloudResource",
            selector=AzureCloudResourceSelector(
                query="true",
                resourceKinds={
                    "Microsoft.Storage/storageAccounts": "2023-01-01",
                    "Microsoft.Compute/virtualMachines": "2023-03-01",
                },
            ),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )

        result = get_resource_configs_with_resource_kind(
            resource_kind="Microsoft.Storage/storageAccounts",
            resource_configs=[config],
        )

        assert len(result) == 1
        assert result[0].kind == ResourceKindsWithSpecialHandling.CLOUD_RESOURCE

    def test_returns_empty_list_for_no_matches(self) -> None:
        """Test returns empty list when no configs match"""
        result = get_resource_configs_with_resource_kind(
            resource_kind="Microsoft.Storage/storageAccounts",
            resource_configs=[],
        )

        assert len(result) == 0
        assert isinstance(result, list)
