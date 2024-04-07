import typing

from azure.core.credentials_async import AsyncTokenCredential
from azure.mgmt.resource.resources.v2022_09_01.aio import ResourceManagementClient

from azure_integration.azure_patch import list_resources
from azure_integration.ocean import loop_over_extension_resource_kind
from azure_integration.utils import (
    batch_resources_iterator,
    resource_client_context,
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
                f"Yielding a batch of {len(resource_groups_batch)} resource groups"
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
                f"Yielding a batch of {resource_kind} in subscription {subscription_id}, found {len(resources_batch)} resources in the batch"
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
            async for resource_batch in loop_over_extension_resource_kind(
                client=resource_management_client,
                full_resource_kind=resource_kind,
                kind_level=1,
                resource_id=resource.id,
                api_version=api_version,
            ):
                yield resource_batch
