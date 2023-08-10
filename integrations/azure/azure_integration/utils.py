import typing

from port_ocean.context.event import event
from port_ocean.ocean import ocean

from azure_integration.overrides import AzurePortAppConfig

BATCH_SIZE = 20


def get_integration_subscription_id() -> str:
    logic_settings = ocean.integration_config
    subscription_id = logic_settings.get("subscription_id", "")
    return subscription_id


async def get_port_resource_configuration_by_kind(kind: str) -> dict:
    app_config = typing.cast(AzurePortAppConfig, event.port_app_config)
    for resource in app_config.resources:
        if resource.kind == kind:
            return resource.dict()
    return {}


def resolve_resource_type_from_cloud_event(cloud_event: dict) -> str:
    """
    Resolves the resource type from the cloud event payload

    example of resource_uri in the event payload:
    /subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/myResourceGroup/providers/Microsoft.Compute/virtualMachines/myVM

    pattern: /subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/{resourceProviderNamespace}/{resourceType}/{resourceName}

    :param cloud_event: Cloud event payload
    :return: Resource type
    """
    resource_uri = cloud_event["data"]["resourceUri"]
    resource = resource_uri.split("/")
    if len(resource) < 8:
        return ""
    resource_type = f"{resource[6]}/{resource[7]}"
    return resource_type


async def batch_iterate_resources_list(
    async_list_method: typing.Callable[..., typing.AsyncIterable], **kwargs
) -> typing.AsyncIterable:
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
