import contextlib
import enum
import typing

from port_ocean.context.event import event
from azure.identity.aio import DefaultAzureCredential
from azure.mgmt.resource.resources.v2022_09_01.aio import ResourceManagementClient

from azure_integration.overrides import (
    AzureSpecificKindsResourceConfig,
    AzureCloudResourceConfig,
    AzureCloudResourceSelector,
    AzureSpecificKindSelector,
)

BATCH_SIZE = 20


class ResourceKindsWithSpecialHandling(enum.StrEnum):
    """
    Resource kinds with special handling
    These resource kinds are handled separately from the other resource kinds
    """

    RESOURCE_GROUPS = "Microsoft.Resources/resourceGroups"
    SUBSCRIPTION = "subscription"
    CLOUD_RESOURCE = "cloudResource"


def get_current_resource_config() -> (
    typing.Union[AzureSpecificKindsResourceConfig, AzureCloudResourceConfig]
):
    """
    Returns the current resource config, accessible only inside an event context
    """
    # for some reason mypy doesn't recognize the `resource_config` as defined in the event context, ignoring it
    return event.resource_config  # type: ignore


def resolve_resource_type_from_resource_uri(resource_uri: str) -> str:
    """
    Resolves the resource type from azure resource uri

    example of resource_uri:
    /subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/myResourceGroup/providers/Microsoft.Compute/virtualMachines/myVM

    pattern: /subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/{resourceProviderNamespace}/{resourceType}/{resourceName}

    :param resource_uri: Azure resource uri
    :return: Resource type
    """
    resource = resource_uri.split("/")
    if len(resource) < 8:
        # Assuming that it is a resource group and not a resource
        # example: /subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/myResourceGroup
        return ResourceKindsWithSpecialHandling.RESOURCE_GROUPS

    elif len(resource) == 8:
        # Assuming that it is a resource
        resource_type = "/".join(resource[6:])
    else:
        # Assuming that it is an extension resource (e.g Microsoft.Storage/storageAccounts/blobServices/containers)
        # For that we need to remove the parent resources names from the resource uri to construct the resource type
        # example:
        # resource_uri = /subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/myResourceGroup/providers/Microsoft.Storage/storageAccounts/myStorageAccount/blobServices/default/containers/myContainer
        # resource_type = Microsoft.Storage/storageAccounts/blobServices/containers
        resource_type = "/".join(resource[6:8])
        # start from the first extension resource kind
        for resource_kind_extension in range(len(resource[9:])):
            # we want to skip the resource name and only add the extension resource kinds
            if resource_kind_extension % 2 == 0:
                resource_type += "/" + resource[9:][resource_kind_extension]

    return resource_type


def get_resource_configs_with_resource_kind(
    resource_kind: str,
    resource_configs: typing.List[
        typing.Union[AzureSpecificKindsResourceConfig, AzureCloudResourceConfig]
    ],
) -> typing.List[
    typing.Union[AzureSpecificKindsResourceConfig, AzureCloudResourceConfig]
]:
    """
    Returns the resource configs that have the resource kind

    :param resource_kind: Resource kind
    :param resource_configs: List of resource configs
    :return: List of resource configs that have the resource kind
    """
    return [
        resource_config
        for resource_config in resource_configs
        if (
            resource_config.kind == resource_kind
            and isinstance(resource_config.selector, AzureSpecificKindSelector)
        )
        or (
            resource_config.kind == ResourceKindsWithSpecialHandling.CLOUD_RESOURCE
            and isinstance(resource_config.selector, AzureCloudResourceSelector)
            and resource_kind in resource_config.selector.resource_kinds.keys()
        )
    ]


def is_sub_resource(resource_type: str) -> bool:
    """
    Checks if the resource type is a sub resource

    Microsoft.Sql/servers/databases is a sub resource of Microsoft.Sql/servers
    Microsoft.Sql/servers is not a sub resource

    :param resource_type: Resource type
    :return: True if the resource type is a sub resource, False otherwise
    """
    return len(resource_type.split("/")) > 2


def get_resource_kind_by_level(
    resource_kind: str, level: int = 0
) -> typing.Tuple[str, bool]:
    """
    Returns the resource kind by level and a boolean indicating if the resource kind is the last level

    example of resource_kind:
    Microsoft.Storage/storageAccounts/blobServices/containers

    level 0: Microsoft.Storage/storageAccounts
    level 1: Microsoft.Storage/storageAccounts/blobServices
    level 2: Microsoft.Storage/storageAccounts/blobServices/containers
    """
    base_level_index = 2
    resource_kind_list = resource_kind.split("/")
    is_last_level = len(resource_kind_list) == base_level_index + level
    return "/".join(resource_kind_list[: base_level_index + level]), is_last_level


async def batch_resources_iterator(
    async_list_method: typing.Callable[..., typing.AsyncIterable[typing.Any]],
    **kwargs: typing.Any,
) -> typing.AsyncIterable[typing.List[typing.Any]]:
    """
    Iterates over the list method of the resources client and yields a list of resources.

    :param async_list_method: The list method of the resources client
    :param kwargs: Any additional arguments that need to be passed to the list method
    :return: A list of resources
    """
    counter = 0
    resource_list = []
    async for resource in async_list_method(**kwargs):
        counter += 1
        resource_list.append(resource.as_dict())
        if counter == BATCH_SIZE:
            yield resource_list
            counter = 0
            resource_list = []
    yield resource_list


@contextlib.asynccontextmanager
async def resource_client_context(
    subscription_id: str,
) -> typing.AsyncIterator[ResourceManagementClient]:
    """
    Creates a resource client context manager that yields a resource client with the default azure credentials
    """
    async with DefaultAzureCredential() as credential:
        async with ResourceManagementClient(
            credential=credential,
            subscription_id=subscription_id,
        ) as client:
            yield client
