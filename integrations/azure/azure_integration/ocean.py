from requests import Request

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource.resources.v2022_09_01.aio import ResourceManagementClient

from utils import (
    get_integration_subscription_id,
    get_port_resource_configuration_by_kind,
    resolve_resource_type_from_cloud_event,
)


@ocean.on_resync()
async def on_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    resource_client = ResourceManagementClient(
        credential=DefaultAzureCredential(),
        subscription_id=get_integration_subscription_id(),
    )
    async for base_resource in resource_client.resources.list(
        filter=f"resourceType eq '{kind}'",
    ):
        resource_config = get_port_resource_configuration_by_kind(kind)
        resource = await resource_client.resources.get_by_id(
            resource_id=base_resource.id,
            api_version=resource_config["selector"]["api_version"],
        )
        yield resource.as_dict()


@ocean.router.post("/azure/events")
async def handle_events(request: Request):
    event = await request.json()
    resource_type = resolve_resource_type_from_cloud_event(event)
    resource_config = get_port_resource_configuration_by_kind(resource_type)
    resource_client = ResourceManagementClient(
        credential=DefaultAzureCredential(),
        subscription_id=get_integration_subscription_id(),
    )
    resource = await resource_client.resources.get_by_id(
        resource_id=event["resourceId"],
        api_version=resource_config["selector"]["api_version"],
    )
    await ocean.register_raw(resource_type, [resource.as_dict()])
