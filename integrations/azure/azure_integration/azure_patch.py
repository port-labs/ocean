from typing import Any, Optional, AsyncIterable

import azure.mgmt.resource.resources.v2022_09_01.aio.operations._operations
from azure.mgmt.resource.resources.v2022_09_01.aio import ResourceManagementClient
from azure.core.rest import HttpRequest
from azure.mgmt.resource.resources.v2022_09_01.operations._operations import (
    _SERIALIZER,
)
from azure.mgmt.subscription._vendor import _format_url_section
from loguru import logger


def build_full_resources_list_request_patch(
    subscription_id: str,
    *,
    filter: Optional[str] = None,
    expand: Optional[str] = None,
    top: Optional[int] = None,
    **kwargs: Any,
) -> HttpRequest:
    """
    Builds the request for the resources list request that will query the resource provider instead of the resources api

    The original request that is being built is:
    GET https://management.azure.com/subscriptions/{subscriptionId}/resources?api-version={apiVersion}
    The original request is querying the resources api which returns a list of resources with only the resource ID and
     resource type.

    The request that we want to build is:
    GET https://management.azure.com/subscriptions/{subscriptionId}/providers/{resourceType}?api-version={apiVersion}
    The request is querying the resource provider which returns a list of resources with all the properties.

    The resource type and api version are passed as headers to the request and are popped from the headers before the
    request is built.
    This is done because there is no way to pass the resource type and api version to the request builder due to the
    way the request builder is being called inside the list method.
    """
    # Build the original request and the HttpRequest object
    request: HttpRequest = old_build_resources_list_request(
        subscription_id=subscription_id, filter=filter, expand=expand, top=top, **kwargs
    )

    resource_type = request.headers.pop("resource-type", None)
    resource_url = request.headers.pop("resource-url", None)

    api_version = request.headers.pop("api-version", None)
    if resource_type:
        # Build the url
        url = "/subscriptions/{subscriptionId}/providers/{resourceType}?api-version={apiVersion}"
        path_format_arguments = {
            "subscriptionId": _SERIALIZER.url(
                "subscription_id", subscription_id, "str", min_length=1
            ),
            "resourceType": _SERIALIZER.url("resource-type", resource_type, "str"),
            "apiVersion": _SERIALIZER.url("api-version", api_version, "str"),
        }
        # Format the url
        url = _format_url_section(url, **path_format_arguments)
        # Override the original url in the request
        request.url = url
    elif resource_url:
        # Build the url
        url = "{resourceUrl}?api-version={apiVersion}"
        path_format_arguments = {
            "resourceUrl": _SERIALIZER.url("resource-url", resource_url, "str"),
            "apiVersion": _SERIALIZER.url("api-version", api_version, "str"),
        }
        # Format the url
        url = _format_url_section(url, **path_format_arguments)
        # Override the original url in the request
        request.url = url
    return request


async def list_resources(
    resources_client: ResourceManagementClient,
    api_version: str,
    resource_type: str = "",
    resource_url: str = "",
) -> AsyncIterable[Any]:
    """
    A list implementation that takes advantage of the patch implemented in this file.
    There are two ways to use this method:
    1. Pass the resource type and api version to the method, and it will query the resource provider
        This is suitable for resource types that are not sub resources (Microsoft.Sql/servers) and can be queried in a
        subscription scope.
        example:
        resource_type = "Microsoft.storage/storageAccounts"
        api_version = "2023-01-01"

        Those params will result the following request:
        (https://management.azure.com/subscriptions/{subscriptionId}/providers/{resourceType}?api-version={apiVersion})

    2. Pass the resource url and api version to the method, and it will query the resource provider
        This is suitable for resource types that are sub resources (Microsoft.Sql/servers/databases) and can be queried
        in a resource scope, which means that the resource id of the parent resource is required.
        example:
        Lets say we want to list all containers in a storage account.
        The containers resource type is "Microsoft.storage/storageAccounts/blobServices/containers"
        api_version = "2023-01-01"
        resource_url = "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.Storage/storageAccounts/{storageAccountName}/blobServices/{blobService}/containers"
        The resource url is the resource id of the parent resource + the resource type of the sub resource.
        The resource url can be obtained by querying the parent resource and getting the id property from the response.

        Those params will result the following request:
        (https://management.azure.com/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.Storage/storageAccounts/{storageAccountName}/blobServices/{blobService}/containers?api-version={apiVersion})
    """
    # override the default version in the client to the version that we want to query
    resources_client.resources._config.api_version = api_version
    if resource_type and resource_url:
        raise ValueError("Only one of resource_type and resource_url can be passed")

    logger.debug(
        "Listing resource",
        resource_type=resource_type,
        resource_url=resource_url,
        api_version=api_version,
    )

    async for resource in resources_client.resources.list(
        headers={
            "resource-type": resource_type,
            "resource-url": resource_url,
            "api-version": api_version,
        }
    ):
        yield resource


# Patch the build_resources_list_request method in the resources operations module
# This is done to be able to query the resource provider instead of the resources api
# The original method is being called inside the list method in the resources client
old_build_resources_list_request = (
    azure.mgmt.resource.resources.v2022_09_01.aio.operations._operations.build_resources_list_request  # type: ignore
)
azure.mgmt.resource.resources.v2022_09_01.aio.operations._operations.build_resources_list_request = (  # type: ignore
    build_full_resources_list_request_patch
)
