from port_ocean import run
from azure.identity.aio import DefaultAzureCredential
from azure.storage.queue import QueueClient
from azure.identity import DefaultAzureCredential as DefaultAzureCredentialSync
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.resource.resources.v2022_09_01.aio import ResourceManagementClient
import asyncio
from typing import Any, Optional

# import azure.mgmt.resource.resources.v2022_09_01.aio.operations._operations
# from azure.mgmt.resource.resources.v2022_09_01.aio import ResourceManagementClient
# from azure.core.rest import HttpRequest
# from azure.mgmt.resource.resources.v2022_09_01.operations._operations import (
#     _format_url_section,
#     _SERIALIZER,
# )
# from loguru import logger
#
#
# def build_full_resources_list_request_patch(
#     subscription_id: str,
#     *,
#     filter: Optional[str] = None,
#     expand: Optional[str] = None,
#     top: Optional[int] = None,
#     **kwargs: Any,
# ) -> HttpRequest:
#     """
#     Builds the request for the resources list request that will query the resource provider instead of the resources api
#
#     The original request that is being built is:
#     GET https://management.azure.com/subscriptions/{subscriptionId}/resources?api-version={apiVersion}
#     The original request is querying the resources api which returns a list of resources with only the resource ID and
#      resource type.
#
#     The request that we want to build is:
#     GET https://management.azure.com/subscriptions/{subscriptionId}/providers/{resourceType}?api-version={apiVersion}
#     The request is querying the resource provider which returns a list of resources with all the properties.
#
#     The resource type and api version are passed as headers to the request and are popped from the headers before the
#     request is built.
#     This is done because there is no way to pass the resource type and api version to the request builder due to the
#     way the request builder is being called inside the list method.
#     """
#     # Build the original request and the HttpRequest object
#     request: HttpRequest = old_build_resources_list_request(
#         subscription_id=subscription_id, filter=filter, expand=expand, top=top, **kwargs
#     )
#
#     resource_type = request.headers.pop("resource-type", None)
#     if resource_type:
#         api_version = request.headers.pop("api-version", None)
#         # Build the url
#         url = "/subscriptions/{subscriptionId}/providers/{resourceType}?api-version={apiVersion}"
#         path_format_arguments = {
#             "subscriptionId": _SERIALIZER.url(
#                 "subscription_id", subscription_id, "str", min_length=1
#             ),
#             "resourceType": _SERIALIZER.url("resource-type", resource_type, "str"),
#             "apiVersion": _SERIALIZER.url("api-version", api_version, "str"),
#         }
#         # Format the url
#         url = _format_url_section(url, **path_format_arguments)
#         # Override the original url in the request
#         request.url = url
#     return request
#
#
# async def list_resources(
#     resources_client: ResourceManagementClient, resource_type: str, api_version: str
# ):
#     """
#     A list implementation that takes advantage of the patch implemented in this file.
#     To be able to use this implementation, the resource type and api version must be passed as headers to the request.
#     """
#     # override the default version in the client to the version that we want to query
#     resources_client.resources._config.api_version = api_version
#     async for resource in resources_client.resources.list(
#         headers={"resource-type": resource_type, "api-version": api_version}
#     ):
#         logger.debug(
#             "Found resource",
#             resource_id=resource.id,
#             kind=resource_type,
#             api_version=api_version,
#         )
#         yield resource
#
#
# # Patch the build_resources_list_request method in the resources operations module
# # This is done to be able to query the resource provider instead of the resources api
# # The original method is being called inside the list method in the resources client
# old_build_resources_list_request = (
#     azure.mgmt.resource.resources.v2022_09_01.aio.operations._operations.build_resources_list_request
# )
# azure.mgmt.resource.resources.v2022_09_01.aio.operations._operations.build_resources_list_request = (
#     build_full_resources_list_request_patch
# )
#
#
# async def main():
#     async with DefaultAzureCredential() as credential:
#         async with ResourceManagementClient(
#             credential=credential,
#             subscription_id="7026e601-6a3b-4210-a9d6-b8742aa3b9f9",
#         ) as client:
#             async for resource in client.resources.list(
#                 filter="resourceType eq 'Microsoft.Sql/servers/databases'"
#             ):
#                 resource = resource.as_dict()
#                 print(resource)
#                 resource_id = resource["id"].split("/")
#                 print(resource["type"], resource_id[5:-1], resource["id"])
#     resource_type = "Microsoft.Sql/servers/databases"
#     resource_chief_type = resource_type.split("/")[:2]
#     resource_sub_type = resource_type.split("/")[-1]
#     async with DefaultAzureCredential() as credential:
#         async with ResourceManagementClient(
#             credential=credential,
#             subscription_id="7026e601-6a3b-4210-a9d6-b8742aa3b9f9",
#         ) as client:
#             async for resource in client.resources.list(
#                 resource_type=resource_chief_type,
#                 api_version="2023-01-01",
#             ):
#                 async for subset_resource in client.resources.list(
#                     resource_url=f"{resource.id}/{resource_sub_type}",
#                     api_version="2023-02-01-preview",
#                 ):
#                     print(subset_resource.as_dict())
#             # async for resource_group in client.resource_groups.list():
#             #     async with ResourceManagementClient(
#             #         credential=credential,
#             #         subscription_id="7026e601-6a3b-4210-a9d6-b8742aa3b9f9",
#             #     ) as resource_mgmt_client:
#             #         async for resource_chief in resource_mgmt_client.resources.list(
#             #                 resource_type=resource_chief_type,
#             #                 api_version="2023-01-01",
#             #         ):
#             #             async for resource in
#

if __name__ == "__main__":
    run()
    # asyncio.run(main())
