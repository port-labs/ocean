import typing

from azure.core.credentials_async import AsyncTokenCredential
from azure.mgmt.resource.resources.v2022_09_01.aio import ResourceManagementClient

from azure_integration.azure_patch import list_resources
from azure_integration.utils import (
    batch_resources_iterator,
    get_resource_kind_by_level,
)
from loguru import logger


async def resource_group_iterator(
    credential: AsyncTokenCredential,
    subscription_id: str,
    api_version: str,
) -> typing.AsyncIterable[typing.List[typing.Any]]:
    """
    Iterates over all the resources in a resource group
    """
    logger.info(
        f"Starting to iterate over all resource groups in subscription {subscription_id}"
    )
    async with ResourceManagementClient(
        credential=credential,
        subscription_id=subscription_id,
    ) as resource_management_client:
        async for resource_groups_batch in batch_resources_iterator(
            resource_management_client.resource_groups.list,
            api_version=api_version,
        ):
            logger.info(
                f"Yielding a batch of {len(resource_groups_batch)} resource groups in subscription {subscription_id}"
            )
            yield resource_groups_batch


async def resource_base_kind_iterator(
    credential: AsyncTokenCredential,
    subscription_id: str,
    resource_kind: str,
    api_version: str,
) -> typing.AsyncIterable[typing.List[typing.Any]]:
    """
    Iterates over all the resources in a resource base kind
    """
    logger.info(
        f"Starting to iterate over all the resources of kind: {resource_kind} in subscription {subscription_id}"
    )
    async with ResourceManagementClient(
        credential=credential,
        subscription_id=subscription_id,
    ) as resource_management_client:
        async for resources_batch in batch_resources_iterator(
            list_resources,
            resources_client=resource_management_client,
            resource_type=resource_kind,
            api_version=api_version,
        ):
            logger.info(
                f"Yielding a batch of {len(resources_batch)} {resource_kind} in subscription {subscription_id}"
            )
            yield resources_batch


async def resource_extention_kind_iterator(
    credential: AsyncTokenCredential,
    subscription_id: str,
    resource_kind: str,
    api_version: str,
) -> typing.AsyncIterable[typing.List[typing.Any]]:
    """
    Iterates over all the resources in a resource extention kind
    """
    logger.info(
        f"Starting to iterate over all the resources of kind: {resource_kind} in subscription {subscription_id}"
    )
    async with ResourceManagementClient(
        credential=credential,
        subscription_id=subscription_id,
    ) as resource_management_client:
        base_resource_kind, _ = get_resource_kind_by_level(resource_kind, 0)
        logger.info(
            f"Listing resources for kind {resource_kind} in subscription {subscription_id}"
        )
        async for resource in list_resources(
            resource_management_client,
            api_version=api_version,
            resource_type=base_resource_kind,
        ):
            async for resource_batch in _loop_over_extension_resource_kind(
                client=resource_management_client,
                full_resource_kind=resource_kind,
                kind_level=1,
                resource_id=resource.id,
                api_version=api_version,
            ):
                yield resource_batch


async def _loop_over_extension_resource_kind(
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
            async for resource_batch in _loop_over_extension_resource_kind(
                client=client,
                full_resource_kind=full_resource_kind,
                kind_level=kind_level + 1,
                resource_id=resource.id,
                api_version=api_version,
            ):
                yield resource_batch
