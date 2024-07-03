import http
import os
import typing

from cloudevents.pydantic import CloudEvent
import fastapi
from loguru import logger
from starlette import responses

from azure_integration.iterators import (
    resource_group_iterator,
    resource_base_kind_iterator,
    resource_extention_kind_iterator,
)
from azure_integration.overrides import (
    AzurePortAppConfig,
    AzureSpecificKindSelector,
    AzureCloudResourceSelector,
)
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from azure.identity.aio import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.subscription.aio import SubscriptionClient

from azure_integration.utils import (
    ResourceKindsWithSpecialHandling,
    resource_client_context,
    resolve_resource_type_from_resource_uri,
    batch_resources_iterator,
    is_sub_resource,
    get_current_resource_config,
    get_resource_configs_with_resource_kind,
)


def _resolve_resync_method_for_resource(
    kind: str,
) -> typing.Callable[..., ASYNC_GENERATOR_RESYNC_TYPE]:
    if is_sub_resource(kind):
        return resync_extension_resources
    return resync_base_resources


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind in iter(ResourceKindsWithSpecialHandling):
        logger.info("Kind already has a specific handling, skipping", kind=kind)
        return
    resource_selector = typing.cast(
        AzureSpecificKindSelector, get_current_resource_config().selector
    )
    iterator_resync_method = _resolve_resync_method_for_resource(kind)
    async for resources_batch in iterator_resync_method(
        kind, resource_selector.api_version
    ):
        yield resources_batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.RESOURCE_GROUPS)
async def resync_resource_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Re-syncs resource groups, this is done separately because the resource groups api is different from the other apis
    """
    resource_selector = typing.cast(
        AzureSpecificKindSelector, get_current_resource_config().selector
    )
    async with DefaultAzureCredential() as credential:
        async with SubscriptionClient(credential=credential) as subscription_client:
            async for subscriptions_batch in batch_resources_iterator(
                subscription_client.subscriptions.list,
            ):
                if subscriptions_batch:
                    tasks = [
                        resource_group_iterator(
                            credential=credential,
                            subscription_id=subscription["subscription_id"],
                            api_version=resource_selector.api_version,
                        )
                        for subscription in subscriptions_batch
                    ]
                    async for resource_groups_batch in stream_async_iterators_tasks(
                        *tasks
                    ):
                        yield resource_groups_batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.SUBSCRIPTION)
async def resync_subscriptions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Re-syncs subscriptions, this is done separately because the subscriptions api is different from the other apis
    """
    async with DefaultAzureCredential() as credential:
        async with SubscriptionClient(credential=credential) as subscription_client:
            async for subscriptions_batch in batch_resources_iterator(
                subscription_client.subscriptions.list,
            ):
                yield subscriptions_batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.CLOUD_RESOURCE)
async def resync_cloud_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    resource_kinds = typing.cast(
        AzureCloudResourceSelector, get_current_resource_config().selector
    ).resource_kinds
    for resource_kind, resource_api_version in resource_kinds.items():
        iterator_resync_method = _resolve_resync_method_for_resource(resource_kind)
        async for resources_batch in iterator_resync_method(
            resource_kind, resource_api_version
        ):
            yield resources_batch


async def resync_base_resources(
    kind: str, api_version: str
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async with DefaultAzureCredential() as credential:
        async with SubscriptionClient(credential=credential) as subscription_client:
            async for subscriptions_batch in batch_resources_iterator(
                subscription_client.subscriptions.list,
            ):
                tasks = [
                    resource_base_kind_iterator(
                        credential=credential,
                        subscription_id=subscription["subscription_id"],
                        resource_kind=kind,
                        api_version=api_version,
                    )
                    for subscription in subscriptions_batch
                ]
                async for resources_batch in stream_async_iterators_tasks(*tasks):
                    yield resources_batch


async def resync_extension_resources(
    kind: str, api_version: str
) -> ASYNC_GENERATOR_RESYNC_TYPE:
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
    :param api_version: The api version to use when querying the resources
    :return: Async generator of extension resources
    """
    with logger.contextualize(resource_kind=kind):
        async with DefaultAzureCredential() as credential:
            async with SubscriptionClient(credential=credential) as subscription_client:
                async for subscriptions_batch in batch_resources_iterator(
                    subscription_client.subscriptions.list,
                ):
                    tasks = [
                        resource_extention_kind_iterator(
                            credential=credential,
                            subscription_id=subscription["subscription_id"],
                            resource_kind=kind,
                            api_version=api_version,
                        )
                        for subscription in subscriptions_batch
                    ]
                    async for resources_batch in stream_async_iterators_tasks(*tasks):
                        yield resources_batch


@ocean.router.post("/events")
async def handle_events(cloud_event: CloudEvent) -> fastapi.Response:
    """
    Handles System events from Azure Event Grid by the Azure subscription resource and registers them in Port
    The event payload is a CloudEvent
    https://learn.microsoft.com/en-us/azure/event-grid/event-schema-subscriptions?tabs=event-grid-event-schema
    https://learn.microsoft.com/en-us/azure/event-grid/cloud-event-schema
    """
    cloud_event_data: dict[str, typing.Any] = cloud_event.data  # type: ignore
    subscription_id = cloud_event_data["subscriptionId"]
    resource_uri = cloud_event_data["resourceUri"]
    logger.info(
        f"Received event {cloud_event.id} of type {cloud_event.type} with operation {cloud_event_data['operationName']} for resource {resource_uri}",
        event_id=cloud_event.id,
        event_type=cloud_event.type,
        resource_provider=cloud_event_data["resourceProvider"],
        operation_name=cloud_event_data["operationName"],
        subscription_id=subscription_id,
    )
    resource_type = resolve_resource_type_from_resource_uri(
        resource_uri=resource_uri,
    )
    if not resource_type:
        logger.warning(
            "Could not resolve resource type from cloud event",
            resource_uri=resource_uri,
        )
        return fastapi.Response(status_code=http.HTTPStatus.NOT_FOUND)

    matching_resource_configs = get_resource_configs_with_resource_kind(
        resource_kind=resource_type,
        resource_configs=typing.cast(
            AzurePortAppConfig, event.port_app_config
        ).resources,
    )
    if not matching_resource_configs:
        logger.info(
            "Resource type not found in port app config, update port app config to include the resource type",
            resource_type=resource_type,
        )
        return fastapi.Response(status_code=http.HTTPStatus.NOT_FOUND)

    async with resource_client_context(subscription_id) as client:
        for resource_config in matching_resource_configs:
            if isinstance(resource_config.selector, AzureSpecificKindSelector):
                api_version = resource_config.selector.api_version
            else:
                api_version = resource_config.selector.resource_kinds[resource_type]
            blueprint = resource_config.port.entity.mappings.blueprint.strip('"')
            logger.info(
                f"Querying full resource details for resource {resource_uri}, api version {api_version} for kind {resource_type} in subscription {subscription_id}"
            )
            try:
                resource = await client.resources.get_by_id(
                    resource_id=resource_uri,
                    api_version=api_version,
                )
                await ocean.register_raw(
                    resource_config.kind, [dict(resource.as_dict())]
                )
            except ResourceNotFoundError:
                logger.info(
                    "Resource not found in azure, unregistering from port",
                    id=resource_uri,
                    kind=resource_config.kind,
                    api_version=api_version,
                    blueprint=blueprint,
                )
                await ocean.unregister(
                    [
                        Entity(
                            blueprint=blueprint,
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


@ocean.on_start()
async def on_start() -> None:
    logger.info("Setting up credentials for Azure client")
    azure_client_id = ocean.integration_config.get("azure_client_id")
    azure_client_secret = ocean.integration_config.get("azure_client_secret")
    azure_tenant_id = ocean.integration_config.get("azure_tenant_id")
    if not azure_client_id or not azure_client_secret or not azure_tenant_id:
        logger.info(
            "Integration wasn't provided with override configuration for initializing client, proceeding with default"
        )
        return

    if azure_client_id:
        logger.info(
            "Detected Azure client id, setting up environment variable for client id"
        )
        os.environ["AZURE_CLIENT_ID"] = azure_client_id
    if azure_client_secret:
        logger.info(
            "Detected Azure client secret, setting up environment variable for client secret"
        )
        os.environ["AZURE_CLIENT_SECRET"] = azure_client_secret
    if azure_tenant_id:
        logger.info(
            "Detected Azure tenant id, setting up environment variable for tenant id"
        )
        os.environ["AZURE_TENANT_ID"] = azure_tenant_id
    logger.info("Azure client credentials set up")
