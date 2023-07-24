import re

from port_ocean.context.ocean import ocean
from overrides import AzurePortAppConfig
from exceptions import AzureIntegrationNotFoundKindInPortAppConfig


def get_integration_subscription_id() -> str:
    logic_settings = ocean.integration_config
    return logic_settings["subscriptionId"]


def get_port_resource_configuration_by_kind(kind: str) -> dict:
    app_config: AzurePortAppConfig = (
        ocean.integration.port_app_config_handler.get_port_app_config()
    )
    for resource in app_config.resources:
        if resource.kind == kind:
            return resource.dict()
    raise AzureIntegrationNotFoundKindInPortAppConfig(
        f"kind {kind} was not found in port app config"
    )


def resolve_resource_type_from_cloud_event(event: dict) -> str:
    """
    Resolves the resource type from the cloud event payload

    example of resource_uri in the event payload:
    /subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/myResourceGroup/providers/Microsoft.Compute/virtualMachines/myVM

    pattern: /subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/{resourceProviderNamespace}/{resourceType}/{resourceName}

    :param event: Cloud event payload
    :return: Resource type
    """
    pattern = r"/subscriptions/(?P<guid>[^/]+)/resourceGroups/(?P<resource_group_name>[^/]+)/(?P<resource_provider_namespace>[^/]+)/(?P<resource_type>.+)/(?P<resource_name>[^/]+)"
    resource_uri = event["data"]["resourceUri"]
    match = re.match(pattern, resource_uri)
    resource_type = match.group("resource_type")
    return resource_type
