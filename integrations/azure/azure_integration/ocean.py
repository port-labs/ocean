import http
import typing

from cloudevents.pydantic import CloudEvent
import fastapi
from loguru import logger
from starlette import responses

from azure_integration.overrides import AzurePortAppConfig, AzureResourceConfig
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from azure.identity.aio import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.resource.resources.v2022_09_01.aio import ResourceManagementClient


from azure_integration.utils import (
    ResourceKindsWithSpecialHandling,
    resource_client_context,
    get_integration_subscription_id,
    resolve_resource_type_from_resource_uri,
    batch_resources_iterator,
    is_sub_resource,
    get_resource_kind_by_level,
    get_current_resource_config,
)
from azure_integration.azure_patch import list_resources


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind in iter(ResourceKindsWithSpecialHandling):
        logger.info("Kind already has a specific handling, skipping", kind=kind)
        return
    if is_sub_resource(kind):
        iterator_resync_method = resync_extension_resources
    else:
        iterator_resync_method = resync_base_resources
    async for resources_batch in iterator_resync_method(kind):
        yield resources_batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.RESOURCE_GROUPS)
async def resync_resource_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Re-syncs resource groups, this is done separately because the resource groups api is different from the other apis
    """
    async with DefaultAzureCredential() as credential:
        async with ResourceManagementClient(
            credential=credential, subscription_id=get_integration_subscription_id()
        ) as client:
            async for resource_groups_batch in batch_resources_iterator(
                client.resource_groups.list,
                api_version=get_current_resource_config().selector.api_version,
            ):
                yield resource_groups_batch


async def resync_base_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async with resource_client_context() as client:
        async for resources_batch in batch_resources_iterator(
            list_resources,
            resources_client=client,
            resource_type=kind,
            api_version=get_current_resource_config().selector.api_version,
        ):
            yield resources_batch


async def resync_extension_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Re-syncs sub resources

    The Resource Management API does not support listing extension resources
    The only way to list extension resources is to query the base resource and get the extension resources from the response
    This method takes advantage of the fact that the resource id is the same as the resource url,
    and uses it to query the base resource which it uses to get the extension resources

    We support multiple levels of extension resources
    For example:
    Microsoft.Storage/storageAccounts/blobServices/containers is an extension resource, and its parent
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
        async with resource_client_context() as client:
            base_resource_kind, _ = get_resource_kind_by_level(kind, 0)
            api_version = get_current_resource_config().selector.api_version
            async for resource in list_resources(
                client,
                api_version=api_version,
                resource_type=base_resource_kind,
            ):
                async for resource_batch in loop_over_extension_resource_kind(
                    client=client,
                    full_resource_kind=kind,
                    kind_level=1,
                    resource_id=resource.id,
                    api_version=api_version,
                ):
                    yield resource_batch


async def loop_over_extension_resource_kind(
    client: ResourceManagementClient,
    full_resource_kind: str,
    kind_level: int,
    resource_id: str,
    api_version: str,
) -> typing.AsyncGenerator[typing.List[dict[str, typing.Any]], None]:
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
async def handle_events(cloud_event: CloudEvent) -> fastapi.Response:
    """
    Handles System events from Azure Event Grid by the Azure subscription resource and registers them in Port
    The event payload is a CloudEvent
    https://learn.microsoft.com/en-us/azure/event-grid/event-schema-subscriptions?tabs=event-grid-event-schema
    https://learn.microsoft.com/en-us/azure/event-grid/cloud-event-schema
    """
    cloud_event_data: dict[str, typing.Any] = cloud_event.data  # type: ignore
    logger.info(
        "Received azure cloud event",
        event_id=cloud_event.id,
        event_type=cloud_event.type,
        resource_provider=cloud_event_data["resourceProvider"],
        operation_name=cloud_event_data["operationName"],
    )
    resource_uri = cloud_event_data["resourceUri"]
    resource_type = resolve_resource_type_from_resource_uri(
        resource_uri=resource_uri,
    )
    if not resource_type:
        logger.warning(
            "Could not resolve resource type from cloud event",
            resource_uri=resource_uri,
        )
        return fastapi.Response(status_code=http.HTTPStatus.NOT_FOUND)

    matching_resource_configs: typing.List[AzureResourceConfig] = [
        resource
        for resource in typing.cast(AzurePortAppConfig, event.port_app_config).resources
        if resource.kind == resource_type
    ]
    if not matching_resource_configs:
        logger.debug(
            "Resource type not found in port app config, update port app config to include the resource type",
            resource_type=resource_type,
        )
        return fastapi.Response(status_code=http.HTTPStatus.NOT_FOUND)

    async with resource_client_context() as client:
        for resource_config in matching_resource_configs:
            blueprint = resource_config.port.entity.mappings.blueprint.strip('"')
            logger.debug(
                "Querying full resource",
                id=resource_uri,
                kind=resource_type,
                api_version=resource_config.selector.api_version,
                blueprint=blueprint,
            )
            try:
                resource = await client.resources.get_by_id(
                    resource_id=resource_uri,
                    api_version=resource_config.selector.api_version,
                )
                await ocean.register_raw(resource_type, [dict(resource.as_dict())])
            except ResourceNotFoundError:
                logger.info(
                    "Resource not found in azure, unregistering from port",
                    id=resource_uri,
                    kind=resource_type,
                    api_version=resource_config.selector.api_version,
                    blueprint=blueprint,
                )
                await ocean.unregister(
                    [
                        Entity(
                            blueprint=resource_config.port.entity.mappings.blueprint.strip(
                                '"'
                            ),
                            identifier=resource_uri,
                        )
                    ]
                )
    return fastapi.Response(status_code=http.HTTPStatus.OK)


@ocean.app.fast_api_app.middleware("azure_cloud_event")
async def cloud_event_validation_middleware_handler(
    request: fastapi.Request,
    call_next: typing.Callable[[fastapi.Request], typing.Awaitable[responses.Response]],
) -> responses.Response:
    """
    Middleware used to handle cloud event validation requests
    Azure topic subscription expects a 200 response with specific headers
    https://github.com/cloudevents/spec/blob/v1.0/http-webhook.md#42-validation-response
    """
    if request.method == "OPTIONS" and request.url.path.startswith("/integration"):
        logger.info("Detected cloud event validation request")
        headers = {
            "WebHook-Allowed-Rate": "100",
            "WebHook-Allowed-Origin": "*",
        }
        response = fastapi.Response(status_code=200, headers=headers)
        return response

    return await call_next(request)
