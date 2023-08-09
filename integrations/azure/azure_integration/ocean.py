from fastapi import Request
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from azure.identity.aio import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.resource.resources.v2022_09_01.aio import ResourceManagementClient


from azure_integration.utils import (
    get_integration_subscription_id,
    get_port_resource_configuration_by_kind,
    resolve_resource_type_from_cloud_event,
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

    resource_config = await get_port_resource_configuration_by_kind(kind)
    api_version = resource_config["selector"]["api_version"]
    async with DefaultAzureCredential() as credential:
        async with ResourceManagementClient(
            credential=credential, subscription_id=get_integration_subscription_id()
        ) as client:
            logger.debug("Listing resources", kind=kind, api_version=api_version)
            async for resource in list_resources(client, kind, api_version):
                yield resource.as_dict()


@ocean.on_resync(kind="Microsoft.Resources/resourceGroups")
async def resync_resource_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    resource_config = await get_port_resource_configuration_by_kind(kind)
    api_version = resource_config["selector"]["api_version"]
    async with DefaultAzureCredential() as credential:
        async with ResourceManagementClient(
            credential=credential, subscription_id=get_integration_subscription_id()
        ) as client:
            async for resource_group in client.resource_groups.list(
                api_version=api_version
            ):
                logger.debug(
                    "Found resource group",
                    resource_group_id=resource_group.id,
                    kind=kind,
                    api_version=api_version,
                )
                yield resource_group.as_dict()


@ocean.router.post("/events")
async def handle_events(request: Request):
    """
    Handles System events from Azure Event Grid by the Azure subscription resource and registers them in Port
    The event payload is a CloudEvent
    https://learn.microsoft.com/en-us/azure/event-grid/event-schema-subscriptions?tabs=event-grid-event-schema
    https://learn.microsoft.com/en-us/azure/event-grid/cloud-event-schema
    """
    event = await request.json()
    logger.debug(
        "Received azure cloud event",
        event_id=event["id"],
        event_type=event["type"],
        resource_provider=event["data"]["resourceProvider"],
        operation_name=event["data"]["operationName"],
    )
    resource_type = resolve_resource_type_from_cloud_event(event)
    if not resource_type:
        logger.warning(
            "Weren't able to resolve resource type from cloud event",
            resource_uri=event["data"]["resourceUri"],
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
                id=event["data"]["resourceUri"],
                kind=resource_type,
                api_version=resource_config["selector"]["api_version"],
            )
            try:
                resource = await client.resources.get_by_id(
                    resource_id=event["data"]["resourceUri"],
                    api_version=resource_config["selector"]["api_version"],
                )
            except ResourceNotFoundError:
                # TODO: delete from port once ocean adds support to delete per identifier
                logger.warning(
                    "Resource not found",
                    id=event["data"]["resourceUri"],
                    kind=resource_type,
                    api_version=resource_config["selector"]["api_version"],
                )
                return {"ok": False}
    await ocean.register_raw(resource_type, [resource.as_dict()])
    return {"ok": True}
