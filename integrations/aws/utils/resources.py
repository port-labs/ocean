import asyncio
import json
from typing import Any, Literal, List, Dict, Callable
import typing

import aioboto3
from aiobotocore.session import AioSession
from loguru import logger
from utils.misc import (
    CustomProperties,
    ResourceKindsWithSpecialHandling,
    is_access_denied_exception,
    is_resource_not_found_exception,
    CloudControlThrottlingConfig,
    CloudControlClientProtocol,
    AsyncPaginator,
    process_list_in_chunks,
    ResourceGroupsClientProtocol,
)
from utils.aws import get_sessions

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from utils.overrides import AWSResourceConfig
from botocore.config import Config as Boto3Config
from botocore.exceptions import ClientError

RESYNC_WITH_GET_RESOURCE_API_BATCH_SIZE = 10


async def get_account_id_from_session(session: AioSession, region: str) -> str:
    """Get account ID from a session using STS."""
    async with session.create_client("sts", region_name=region) as sts:
        identity = await sts.get_caller_identity()
        return identity["Account"]


def is_global_resource(kind: str) -> bool:
    global_services = [
        "cloudfront",
        "route53",
        "waf",
        "waf-regional",
        "iam",
        "organizations",
        "s3",
    ]
    try:
        service = kind.split("::")[1].lower()
        return service in global_services
    except IndexError:
        return False


def fix_unserializable_date_properties(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))


async def describe_single_resource(
    kind: str,
    identifier: str,
    resource_config: AWSResourceConfig,
    account_id: str | None = None,
    region: str | None = None,
) -> dict[str, str]:
    async for session, session_region in get_sessions(
        resource_config, account_id=account_id
    ):
        current_region = session_region
        match kind:
            case ResourceKindsWithSpecialHandling.ELBV2_LOAD_BALANCER:
                async with session.create_client(
                    "elbv2", region_name=current_region
                ) as elbv2:
                    response = await elbv2.describe_load_balancers(
                        LoadBalancerArns=[identifier]
                    )
                    return fix_unserializable_date_properties(
                        response.get("LoadBalancers")[0]
                    )
            case ResourceKindsWithSpecialHandling.ELASTICACHE_CLUSTER:
                async with session.create_client(
                    "elasticache", region_name=current_region
                ) as elasticache:
                    response = await elasticache.describe_cache_clusters(
                        CacheClusterId=identifier
                    )
                    return fix_unserializable_date_properties(
                        response.get("CacheClusters")[0]
                    )
            case ResourceKindsWithSpecialHandling.ACM_CERTIFICATE:
                async with session.create_client(
                    "acm", region_name=current_region
                ) as acm:
                    response = await acm.describe_certificate(CertificateArn=identifier)
                    resource = response.get("ResourceDescription")
                    return fix_unserializable_date_properties(resource)
            case ResourceKindsWithSpecialHandling.AMI_IMAGE:
                logger.warning(
                    f"Skipping AMI image {identifier} because it's not supported yet"
                )
                return {}
            case ResourceKindsWithSpecialHandling.CLOUDFORMATION_STACK:
                async with session.create_client(
                    "cloudformation", region_name=current_region
                ) as cloudformation:
                    response = await cloudformation.describe_stacks(
                        StackName=identifier
                    )
                    stack = response.get("Stacks")[0]
                    return fix_unserializable_date_properties(stack)
            case _:
                async with session.create_client(
                    "cloudcontrol",
                    region_name=current_region,
                    config=Boto3Config(
                        retries={
                            "max_attempts": CloudControlThrottlingConfig.MAX_RETRY_ATTEMPTS.value,
                            "mode": CloudControlThrottlingConfig.RETRY_MODE.value,
                        },
                    ),
                ) as cloudcontrol:
                    return await describe_single_resource_cloudcontrol(
                        kind, identifier, cloudcontrol
                    )
    return {}


async def describe_single_resource_cloudcontrol(
    kind: str,
    identifier: str,
    client: CloudControlClientProtocol,
) -> dict[str, str]:
    response = await client.get_resource(TypeName=kind, Identifier=identifier)
    resource_description = response["ResourceDescription"]
    serialized = resource_description.copy()
    serialized.update(
        {
            "Properties": json.loads(resource_description.get("Properties")),
        }
    )
    return serialized


async def process_single_cloudcontrol_resource(
    kind: str,
    identifier: str,
    cloudcontrol_client: Any,
    account_id: str,
    region: str,
) -> Dict[str, Any]:
    """
    Process a single resource using the cloudcontrol get resource API.
    Attaches metadata and fixes unserializable properties.
    """
    try:
        response = await describe_single_resource_cloudcontrol(
            kind, identifier, client=cloudcontrol_client
        )
        response |= {
            CustomProperties.KIND.value: kind,
            CustomProperties.ACCOUNT_ID.value: account_id,
            CustomProperties.REGION.value: region,
        }
        return fix_unserializable_date_properties(response)
    except Exception as e:
        logger.error(f"Error processing resource {identifier}: {str(e)}")
        raise


async def process_resources_chunk(
    chunk: List[Any],
    kind: str,
    account_id: str,
    region: str,
    cloudcontrol_client: Any,
    identifier_extractor: Callable[[Any], str] = lambda x: (
        x.get("Identifier", "") if isinstance(x, dict) else x
    ),
) -> List[Dict[Any, Any]]:
    """
    Process a chunk of resources concurrently.
    Uses an extractor to obtain the identifier from each item.
    """
    tasks = [
        process_single_cloudcontrol_resource(
            kind, identifier_extractor(item), cloudcontrol_client, account_id, region
        )
        for item in chunk
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    processed_resources = []
    for res in results:
        if isinstance(res, Exception):
            # If the exception indicates the resource wasn't found, log and skip it.
            if is_resource_not_found_exception(res):
                error = typing.cast(ClientError, res)
                logger.info(
                    f"Skipping resyncing {kind} resource in region {region} in account {account_id}; "
                    f"{error.response['Error']['Message']}"
                )
                continue
            else:
                raise res
        else:
            processed_resources.append(typing.cast(Dict[Any, Any], res))
    return processed_resources


async def resync_sqs_queue(
    kind: str,
    session: AioSession,
    region: str,
    resource_config: AWSResourceConfig,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    account_id = await get_account_id_from_session(session, region)
    resource_config_selector = resource_config.selector
    if not resource_config_selector.is_region_allowed(region):
        logger.info(
            f"Skipping resyncing {kind} in region {region} in account {account_id} because it's not allowed"
        )
        return

    async with session.create_client("sqs", region_name=region) as sqs_client:
        paginator = AsyncPaginator(
            client=sqs_client,
            method_name="list_queues",
            list_param="QueueUrls",
            MaxResults=1000,
        )
        try:
            async with session.create_client(
                "cloudcontrol",
                region_name=region,
                config=Boto3Config(
                    retries={
                        "max_attempts": CloudControlThrottlingConfig.MAX_RETRY_ATTEMPTS.value,
                        "mode": CloudControlThrottlingConfig.RETRY_MODE.value,
                    },
                ),
            ) as cloudcontrol:
                async for page in paginator.paginate():
                    if not page:  # Skip empty pages
                        continue
                    logger.info(
                        f"Received {len(page)} {kind} resources in region {region}"
                    )
                    queues_in_batch = len(page)
                    processed_count = 0
                    # For SQS, each item is a string (the queue URL), so our extractor returns it as is.
                    for chunk in process_list_in_chunks(
                        page, RESYNC_WITH_GET_RESOURCE_API_BATCH_SIZE
                    ):
                        processed_chunk = await process_resources_chunk(
                            chunk,
                            kind,
                            account_id,
                            region,
                            cloudcontrol,
                            identifier_extractor=lambda queue_url: queue_url,  # queue_url is already a string
                        )
                        processed_count += len(chunk)
                        logger.info(
                            f"Processed {processed_count}/{queues_in_batch} {kind} resources in batch from region {region} in account {account_id}"
                        )
                        yield processed_chunk
                    logger.info(
                        f"Finished processing all {kind} resources from region {region} in account {account_id}"
                    )

        except sqs_client.exceptions.ClientError as e:
            if is_access_denied_exception(e):
                logger.warning(
                    f"Skipping resyncing {kind} in region {region} in account {account_id} due to missing access permissions"
                )
            else:
                raise e


async def fetch_group_resources(
    client: ResourceGroupsClientProtocol, group_name: str, region: str
) -> list[dict[str, Any]]:
    resources_paginator = AsyncPaginator(
        client=client,
        method_name="list_group_resources",
        list_param="Resources",
    )

    group_resources = []

    async for resources_batch in resources_paginator.paginate(Group=group_name):
        if resources_batch:
            group_resources.extend(resources_batch)
    return group_resources


async def enrich_group_with_resources(
    client: ResourceGroupsClientProtocol,
    group: dict[str, Any],
    kind: str,
    account_id: str,
    region: str,
) -> dict[str, Any]:
    group_resources = await fetch_group_resources(client, group["Name"], region)

    return {
        CustomProperties.KIND.value: kind,
        CustomProperties.ACCOUNT_ID.value: account_id,
        CustomProperties.REGION.value: region,
        **fix_unserializable_date_properties(group),
        "__Resources": group_resources,
    }


async def resync_resource_group(
    kind: str,
    session: AioSession,
    region: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Batch resources from AWS Resource Groups service, including both the groups and their member resources.
    """
    account_id = await get_account_id_from_session(session, region)

    async with session.create_client(
        "resource-groups",
        region_name=region,
        config=Boto3Config(
            retries={
                "max_attempts": CloudControlThrottlingConfig.MAX_RETRY_ATTEMPTS.value,
                "mode": CloudControlThrottlingConfig.RETRY_MODE.value,
            },
        ),
    ) as client:
        paginator = AsyncPaginator(
            client=client,
            method_name="list_groups",
            list_param="Groups",
        )

        try:
            async for groups_batch in paginator.paginate():
                if not groups_batch:
                    continue
                for chunk_groups in process_list_in_chunks(
                    groups_batch, RESYNC_WITH_GET_RESOURCE_API_BATCH_SIZE
                ):
                    tasks = [
                        enrich_group_with_resources(
                            client, group, kind, account_id, region
                        )
                        for group in chunk_groups
                    ]
                    processed_groups = await asyncio.gather(*tasks)

                    if processed_groups:
                        yield processed_groups
                        logger.info(
                            f"Processed {len(processed_groups)} {kind} resource groups in region {region} for account {account_id}"
                        )

        except client.exceptions.ClientError as e:
            if is_access_denied_exception(e):
                logger.warning(
                    f"Skipping resyncing {kind} in region {region} in account {account_id} due to missing access permissions"
                )
            else:
                raise e


async def resync_custom_kind(
    kind: str,
    session: AioSession,
    region: str,
    service_name: Literal["acm", "elbv2", "cloudformation", "ec2", "elasticache"],
    describe_method: str,
    list_param: str,
    marker_param: Literal["NextToken", "Marker"],
    resource_config: AWSResourceConfig,
    describe_method_params: dict[str, Any] | None = None,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Batch resources from a service that supports pagination
    kind - the kind of resource
    session - the aiobotocore session to use
    region - the AWS region
    service_name - the name of the service
    describe_method - the name of the method to describe the resource
    list_param - the name of the parameter that contains the list of resources
    marker_param - the name of the parameter that contains the next token
    resource_config - the AWSResourceConfig object
    describe_method_params - additional parameters for the describe method
    """
    account_id = await get_account_id_from_session(session, region)
    if not resource_config.selector.is_region_allowed(region):
        logger.info(
            f"Skipping resyncing {kind} in region {region} in account {account_id} because it's not allowed"
        )
        return
    next_token = None
    if not describe_method_params:
        describe_method_params = {}
    async with session.create_client(service_name, region_name=region) as client:
        while True:
            try:
                params: dict[str, Any] = describe_method_params.copy()
                if next_token:
                    params[marker_param] = next_token
                response = await getattr(client, describe_method)(**params)
                next_token = response.get(marker_param)
                results = response.get(list_param, [])
                if results:
                    yield [
                        {
                            CustomProperties.KIND.value: kind,
                            CustomProperties.ACCOUNT_ID.value: account_id,
                            CustomProperties.REGION.value: region,
                            **fix_unserializable_date_properties(resource),
                        }
                        for resource in results
                    ]
                logger.info(
                    f"Processed {len(results)} {kind} resources in region {region} for account {account_id}"
                )
                if not next_token:
                    break
            except client.exceptions.ClientError as e:
                if is_access_denied_exception(e):
                    logger.warning(
                        f"Skipping resyncing {kind} in region {region} due to missing access permissions"
                    )
                    break
                else:
                    raise e


async def resync_cloudcontrol(
    kind: str,
    session: AioSession,
    region: str,
    resource_config: AWSResourceConfig,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    resource_config_selector = resource_config.selector
    use_get_resource_api = resource_config_selector.use_get_resource_api

    account_id = await get_account_id_from_session(session, region)
    if not resource_config_selector.is_region_allowed(region):
        logger.info(
            f"Skipping resyncing {kind} in region {region} in account {account_id} because it's not allowed"
        )
        return

    logger.info(f"Resyncing {kind} in account {account_id} in region {region}")

    async with session.create_client(
        "cloudcontrol", region_name=region
    ) as cloudcontrol_client:
        paginator = AsyncPaginator(
            client=cloudcontrol_client,
            method_name="list_resources",
            list_param="ResourceDescriptions",
        )
        try:
            async for resources_batch in paginator.paginate(TypeName=kind):
                if not resources_batch:
                    continue

                if use_get_resource_api:
                    # Use the get resource API, processing in chunks of RESYNC_WITH_GET_RESOURCE_API_BATCH_SIZE.
                    async with session.create_client(
                        "cloudcontrol",
                        region_name=region,
                        config=Boto3Config(
                            retries={
                                "max_attempts": CloudControlThrottlingConfig.MAX_RETRY_ATTEMPTS.value,
                                "mode": CloudControlThrottlingConfig.RETRY_MODE.value,
                            },
                        ),
                    ) as cloudcontrol_get_resource_client:
                        total_resources = len(resources_batch)
                        processed_count = 0
                        for chunk in process_list_in_chunks(
                            resources_batch, RESYNC_WITH_GET_RESOURCE_API_BATCH_SIZE
                        ):
                            processed_chunk = await process_resources_chunk(
                                chunk,
                                kind,
                                account_id,
                                region,
                                cloudcontrol_get_resource_client,
                            )
                            processed_count += len(chunk)
                            logger.info(
                                f"Processed {processed_count}/{total_resources} {kind} resources in batch from region {region} in account {account_id}"
                            )

                        yield processed_chunk
                else:
                    # If not using get_resource_api, deserialize and update each resource in one go.
                    page_resources = []
                    for instance in resources_batch:
                        serialized = {
                            "Identifier": instance.get("Identifier"),
                            "Properties": json.loads(instance.get("Properties")),
                        }
                        serialized.update(
                            {
                                CustomProperties.KIND.value: kind,
                                CustomProperties.ACCOUNT_ID.value: account_id,
                                CustomProperties.REGION.value: region,
                            }
                        )
                        page_resources.append(
                            fix_unserializable_date_properties(serialized)
                        )
                    logger.info(
                        f"Processed {len(page_resources)} {kind} resources in region {region} for account {account_id}"
                    )
                    yield page_resources
        except Exception as e:
            if is_access_denied_exception(e):
                logger.warning(
                    f"Skipping resyncing {kind} in region {region} in account {account_id} due to missing access permissions"
                )
            else:
                logger.error(f"Error resyncing {kind} in region {region}: {e}")
            raise e
