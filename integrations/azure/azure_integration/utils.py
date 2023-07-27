import typing

from port_ocean.context.event import event
from port_ocean.ocean import ocean

from azure_integration.overrides import AzurePortAppConfig


def get_integration_subscription_id() -> str:
    logic_settings = ocean.integration_config
    # TODO: change once main branch is released as 0.1.3
    subscription_id = logic_settings.get("subscription_id", "") or logic_settings.get(
        "subscriptionId", ""
    )
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
