import http

from cloudevents.pydantic import CloudEvent
import fastapi
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from azure.identity.aio import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.resource.resources.v2022_09_01.aio import ResourceManagementClient


from azure_integration.utils import (
    ResourceKindsWithSpecialHandling,
    resource_client_context,
    get_integration_subscription_id,
    get_port_resource_configuration_by_kind,
    resolve_resource_type_from_resource_uri,
    batch_resources_iterator,
    is_sub_resource,
    get_resource_kind_by_level,
)
from azure_integration.azure_patch import list_resources


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(resource_kind=kind):
        logger.info("Entered resync of base resources", kind=kind)
        if kind in iter(ResourceKindsWithSpecialHandling) or is_sub_resource(kind):
            logger.info("Kind is not a base resource, skipping resync", kind=kind)
            return

        async with resource_client_context() as client:
            async for resources_batch in batch_resources_iterator(
                list_resources,
                resources_client=client,
                resource_type=kind,
                api_version=event.resource_config.selector.api_version,
            ):
                yield resources_batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.RESOURCE_GROUPS)
async def resync_resource_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Re-syncs resource groups, this is done separately because the resource groups api is different from the other apis
    """
    with logger.contextualize(resource_kind=kind):
        logger.info("Entered resync of resource groups", kind=kind)
        async with DefaultAzureCredential() as credential:
            async with ResourceManagementClient(
                credential=credential, subscription_id=get_integration_subscription_id()
            ) as client:
                async for resource_groups_batch in batch_resources_iterator(
                    client.resource_groups.list,
                    api_version=event.resource_config.selector.api_version,
                ):
                    yield resource_groups_batch


@ocean.on_resync()
async def resync_extension_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Re-syncs sub resources

    The Resource Management API does not support listing extension resources
    The only way to list extension resources is to query the base resource and get the extension resources from the response
    This method take advantage of the fact that the resource id is the same as the resource url,
    and uses it to query the base resource and with like that get the extension resources

    We support multiple levels of extension resources
    For example:
    Microsoft.Storage/storageAccounts/blobServices/containers is an extension resource, and also it parent
    Microsoft.Storage/storageAccounts/blobServices is an extension resource of Microsoft.Storage/storageAccounts
    Microsoft.Storage/storageAccounts is a base resource

    To get the resource "Microsoft.Storage/storageAccounts/blobServices/containers" we need to construct a query like this:
    /subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.Storage/storageAccounts/{storageAccountName}/blobServices/default/containers

    So the way we do it is by splitting the resource kind by "/" and then query the highest level resource and then
    loop over each of the extension resources in the hierarchy until we get to the last extension resource

    Obviously this has a performance impact, but it's the only way to get sub resources in a generic way, without
    having the base resource ids

    :param kind: Resource kind
    :return: Async generator of extension resources
    """
    with logger.contextualize(resource_kind=kind):
        logger.info("Entered resync of extension resources", kind=kind)
        if not is_sub_resource(kind) or kind in iter(ResourceKindsWithSpecialHandling):
            logger.info("Kind is not an extension resource, skipping resync", kind=kind)
            return

        async with resource_client_context() as client:
            base_resource_kind, _ = get_resource_kind_by_level(kind, 0)
            async for resource in list_resources(
                client,
                api_version=event.resource_config.selector.api_version,
                resource_type=base_resource_kind,
            ):
                async for resource_batch in loop_over_extension_resource_kind(
                    client=client,
                    full_resource_kind=kind,
                    kind_level=1,
                    resource_id=resource.id,
                    api_version=event.resource_config.selector.api_version,
                ):
                    yield resource_batch


async def loop_over_extension_resource_kind(
    client: ResourceManagementClient,
    full_resource_kind: str,
    kind_level: int,
    resource_id: str,
    api_version: str,
):
    """
    Loops over a extension resource kind and yields a batch of resources

    This method is called recursively until it reaches the last level of the resource kind, and then it yields a batch
    of resources from the last level.

    :param client: The resource client
    :param full_resource_kind: Full resource kind (Microsoft.Storage/storageAccounts/blobServices/containers)
    :param kind_level: The level of the resource kind
        (0 for Microsoft.Storage/storageAccounts, 1 for Microsoft.Storage/storageAccounts/blobServices, etc)
    :param resource_id: The resource id of the parent resource, used to query the extension resources of the parent resource
        (/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.Storage/storageAccounts/{storageAccountName})
    :param api_version: The api version to use when querying the resources
    """
    current_resource_kind, is_last_level = get_resource_kind_by_level(
        full_resource_kind, kind_level
    )
    current_resource_kind_suffix = current_resource_kind.split("/")[-1]
    list_resource_url = f"{resource_id}/{current_resource_kind_suffix}"
    logger.debug(
        "Looping over resource kind",
        resource_kind=current_resource_kind,
        kind_level=kind_level,
        parent_resource_id=resource_id,
        api_version=api_version,
    )
    if is_last_level:
        async for resource_batch in batch_resources_iterator(
            list_resources,
            resources_client=client,
            api_version=api_version,
            resource_url=list_resource_url,
        ):
            yield resource_batch
    else:
        async for resource in list_resources(
            client,
            api_version=api_version,
            resource_url=list_resource_url,
        ):
            async for resource_batch in loop_over_extension_resource_kind(
                client=client,
                full_resource_kind=full_resource_kind,
                kind_level=kind_level + 1,
                resource_id=resource.id,
                api_version=api_version,
            ):
                yield resource_batch


@ocean.router.post("/events")
async def handle_events(cloud_event: CloudEvent):
    """
    Handles System events from Azure Event Grid by the Azure subscription resource and registers them in Port
    The event payload is a CloudEvent
    https://learn.microsoft.com/en-us/azure/event-grid/event-schema-subscriptions?tabs=event-grid-event-schema
    https://learn.microsoft.com/en-us/azure/event-grid/cloud-event-schema
    """
    logger.debug(
        "Received azure cloud event",
        event_id=cloud_event.id,
        event_type=cloud_event.type,
        resource_provider=cloud_event.data["resourceProvider"],
        operation_name=cloud_event.data["operationName"],
    )
    resource_type = resolve_resource_type_from_resource_uri(
        cloud_event.data["resourceUri"]
    )
    if not resource_type:
        logger.warning(
            "Could not resolve resource type from cloud event",
            resource_uri=cloud_event.data["resourceUri"],
        )
        return fastapi.Response(status_code=http.HTTPStatus.NOT_FOUND)

    resource_config = await get_port_resource_configuration_by_kind(resource_type)
    if not resource_config:
        logger.debug(
            "Resource type not found in port app config, update port app config to include the resource type",
            resource_type=resource_type,
        )
        return fastapi.Response(status_code=http.HTTPStatus.NOT_FOUND)

    async with resource_client_context() as client:
        logger.debug(
            "Querying full resource",
            id=cloud_event.data["resourceUri"],
            kind=resource_type,
            api_version=resource_config.selector.api_version,
        )
        try:
            resource = await client.resources.get_by_id(
                resource_id=cloud_event.data["resourceUri"],
                api_version=resource_config.selector.api_version,
            )
        except ResourceNotFoundError:
            logger.debug(
                "Resource not found in azure, unregistering from port",
                id=cloud_event.data["resourceUri"],
                kind=resource_type,
                api_version=resource_config.selector.api_version,
            )
            await ocean.unregister(
                [
                    Entity(
                        blueprint=resource_config.port.entity.mappings.blueprint,
                        identifier=cloud_event.data["resourceUri"],
                    )
                ]
            )
            return fastapi.Response(status_code=http.HTTPStatus.OK)
    await ocean.register_raw(resource_type, [resource.as_dict()])
    return fastapi.Response(status_code=http.HTTPStatus.OK)
