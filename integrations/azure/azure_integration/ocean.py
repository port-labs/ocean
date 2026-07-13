import os
import typing

import fastapi
from loguru import logger
from starlette import responses

from azure_integration.iterators import (
    resource_group_iterator,
    resource_base_kind_iterator,
    resource_extention_kind_iterator,
)
from azure_integration.overrides import (
    AzureSpecificKindSelector,
    AzureCloudResourceSelector,
)
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from azure.identity.aio import DefaultAzureCredential
from azure.mgmt.resource.subscriptions.aio import SubscriptionClient

from azure_integration.utils import (
    ResourceKindsWithSpecialHandling,
    batch_resources_iterator,
    is_sub_resource,
    get_current_resource_config,
)
from azure_integration.webhook.webhook_processors.resource_event_processor import (
    AzureResourceEventProcessor,
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
    resource_selector = typing.cast(
        AzureSpecificKindSelector, get_current_resource_config().selector
    )
    async with DefaultAzureCredential() as credential:
        async with SubscriptionClient(credential=credential) as subscription_client:
            async for subscriptions_batch in batch_resources_iterator(
                subscription_client.subscriptions.list,
                api_version=resource_selector.api_version,
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
    if request.method == "OPTIONS" and request.scope["path"].startswith("/integration"):
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


ocean.add_webhook_processor("/events", AzureResourceEventProcessor)
