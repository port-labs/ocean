from fastapi import Request
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from azure.identity.aio import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.resource.resources.v2022_09_01.aio import ResourceManagementClient


from azure_integration.utils import (
    get_integration_subscription_id,
    get_port_resource_configuration_by_kind,
    resolve_resource_type_from_cloud_event,
    batch_resources_iterator,
)
from azure_integration.azure_patch import list_resources


RESOURCE_KINDS_WITH_SPECIAL_HANDLING = [
    "Microsoft.Resources/resourceGroups",
]


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind in RESOURCE_KINDS_WITH_SPECIAL_HANDLING:
        logger.debug("Skipping resync", kind=kind)
        return

    async with DefaultAzureCredential() as credential:
        async with ResourceManagementClient(
            credential=credential, subscription_id=get_integration_subscription_id()
        ) as client:
            logger.debug(
                "Listing resources",
                kind=kind,
                api_version=event.resource_config.selector.api_version,
            )
            async for resources_batch in batch_resources_iterator(
                list_resources,
                resources_client=client,
                resource_type=kind,
                api_version=event.resource_config.selector.api_version,
            ):
                yield resources_batch


@ocean.on_resync(kind="Microsoft.Resources/resourceGroups")
async def resync_resource_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async with DefaultAzureCredential() as credential:
        async with ResourceManagementClient(
            credential=credential, subscription_id=get_integration_subscription_id()
        ) as client:
            async for resource_groups_batch in batch_resources_iterator(
                client.resource_groups.list,
                api_version=event.resource_config.selector.api_version,
            ):
                yield resource_groups_batch


@ocean.router.post("/events")
async def handle_events(request: Request):
    """
    Handles System events from Azure Event Grid by the Azure subscription resource and registers them in Port
    The event payload is a CloudEvent
    https://learn.microsoft.com/en-us/azure/event-grid/event-schema-subscriptions?tabs=event-grid-event-schema
    https://learn.microsoft.com/en-us/azure/event-grid/cloud-event-schema
    """
    cloud_evnet = await request.json()
    logger.debug(
        "Received azure cloud event",
        event_id=cloud_evnet["id"],
        event_type=cloud_evnet["type"],
        resource_provider=cloud_evnet["data"]["resourceProvider"],
        operation_name=cloud_evnet["data"]["operationName"],
    )
    resource_type = resolve_resource_type_from_cloud_event(cloud_evnet)
    if not resource_type:
        logger.warning(
            "Weren't able to resolve resource type from cloud event",
            resource_uri=cloud_evnet["data"]["resourceUri"],
        )
        return {"ok": False}

    resource_config = await get_port_resource_configuration_by_kind(resource_type)
    if not resource_config:
        logger.debug(
            "Resource type not found in port app config, update port app config to include the resource type",
            resource_type=resource_type,
        )
        return {"ok": False}

    async with DefaultAzureCredential() as credential:
        async with ResourceManagementClient(
            credential=credential, subscription_id=get_integration_subscription_id()
        ) as client:
            logger.debug(
                "Querying full resource",
                id=cloud_evnet["data"]["resourceUri"],
                kind=resource_type,
                api_version=resource_config["selector"]["api_version"],
            )
            try:
                resource = await client.resources.get_by_id(
                    resource_id=cloud_evnet["data"]["resourceUri"],
                    api_version=resource_config["selector"]["api_version"],
                )
            except ResourceNotFoundError:
                # TODO: delete from port once ocean adds support to delete per identifier
                logger.warning(
                    "Resource not found",
                    id=cloud_evnet["data"]["resourceUri"],
                    kind=resource_type,
                    api_version=resource_config["selector"]["api_version"],
                )
                return {"ok": False}
    await ocean.register_raw(resource_type, [resource.as_dict()])
    return {"ok": True}
