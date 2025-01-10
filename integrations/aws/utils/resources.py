import asyncio
import json
from typing import Any, Literal
import typing

from aiolimiter import AsyncLimiter
import aioboto3
from loguru import logger
from utils.misc import (
    CustomProperties,
    ResourceKindsWithSpecialHandling,
    is_access_denied_exception,
    is_resource_not_found_exception,
    CloudControlThrottlingConfig,
    CloudControlClientProtocol,
)
from utils.aws import get_sessions

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from utils.aws import _session_manager
from utils.overrides import AWSResourceConfig
from botocore.config import Config as Boto3Config
from botocore.exceptions import ClientError


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
    kind: str, identifier: str, account_id: str | None = None, region: str | None = None
) -> dict[str, str]:
    async for session in get_sessions(account_id, region):
        region = session.region_name
        match kind:
            case ResourceKindsWithSpecialHandling.ELBV2_LOAD_BALANCER:
                async with session.client("elbv2") as elbv2:
                    response = await elbv2.describe_load_balancers(
                        LoadBalancerArns=[identifier]
                    )
                    return fix_unserializable_date_properties(
                        response.get("LoadBalancers")[0]
                    )
            case ResourceKindsWithSpecialHandling.ELASTICACHE_CLUSTER:
                async with session.client("elasticache") as elasticache:
                    response = await elasticache.describe_cache_clusters(
                        CacheClusterId=identifier
                    )
                    return fix_unserializable_date_properties(
                        response.get("CacheClusters")[0]
                    )
            case ResourceKindsWithSpecialHandling.ACM_CERTIFICATE:
                async with session.client("acm") as acm:
                    response = await acm.describe_certificate(CertificateArn=identifier)
                    resource = response.get("ResourceDescription")
                    return fix_unserializable_date_properties(resource)
            case ResourceKindsWithSpecialHandling.AMI_IMAGE:
                logger.warning(
                    f"Skipping AMI image {identifier} because it's not supported yet"
                )
                return {}
            case ResourceKindsWithSpecialHandling.CLOUDFORMATION_STACK:
                async with session.client("cloudformation") as cloudformation:
                    response = await cloudformation.describe_stacks(
                        StackName=identifier
                    )
                    stack = response.get("Stacks")[0]
                    return fix_unserializable_date_properties(stack)
            case _:
                async with session.client(
                    "cloudcontrol",
                    config=Boto3Config(
                        retries={
                            "max_attempts": CloudControlThrottlingConfig.MAX_RETRY_ATTEMPTS.value,
                            "mode": CloudControlThrottlingConfig.RETRY_MODE.value,
                        },
                    ),
                ) as cloudcontrol:
                    semaphore = asyncio.BoundedSemaphore(
                        CloudControlThrottlingConfig.SEMAPHORE.value
                    )
                    rate_limiter = AsyncLimiter(
                        CloudControlThrottlingConfig.MAX_RATE.value,
                        CloudControlThrottlingConfig.TIME_PERIOD.value,
                    )
                    return await describe_single_resource_cloudcontrol(
                        kind, identifier, cloudcontrol, semaphore, rate_limiter
                    )
    return {}


async def describe_single_resource_cloudcontrol(
    kind: str,
    identifier: str,
    client: CloudControlClientProtocol,
    semaphore: asyncio.Semaphore,
    rate_limiter: AsyncLimiter,
) -> dict[str, str]:
    async with semaphore:
        async with rate_limiter:
            response = await client.get_resource(TypeName=kind, Identifier=identifier)
            resource_description = response["ResourceDescription"]
            serialized = resource_description.copy()
            serialized.update(
                {
                    "Properties": json.loads(resource_description.get("Properties")),
                }
            )
            return serialized


async def resync_custom_kind(
    kind: str,
    session: aioboto3.Session,
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
    session - the boto3 session to use
    service_name - the name of the service
    describe_method - the name of the method to describe the resource
    list_param - the name of the parameter that contains the list of resources
    marker_param - the name of the parameter that contains the next token
    describe_method_params - additional parameters for the describe method
    """
    region = session.region_name
    account_id = await _session_manager.find_account_id_by_session(session)
    next_token = None

    resource_config_selector = resource_config.selector

    if not resource_config_selector.is_region_allowed(region):
        logger.info(
            f"Skipping resyncing {kind} in region {region} in account {account_id} because it's not allowed"
        )
        return

    if not describe_method_params:
        describe_method_params = {}
    async with session.client(service_name) as client:
        while True:
            try:
                params: dict[str, Any] = describe_method_params
                if next_token:
                    params[marker_param] = next_token
                response = await getattr(client, describe_method)(**params)
                next_token = response.get(marker_param)
                results = response.get(list_param, [])
                logger.info(
                    f"Fetched batch of {len(results)} from {kind} in region {region}"
                )
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
    kind: str, session: aioboto3.Session, resource_config: AWSResourceConfig
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    resource_config_selector = resource_config.selector
    use_get_resource_api = resource_config_selector.use_get_resource_api

    region = session.region_name
    account_id = await _session_manager.find_account_id_by_session(session)
    if not resource_config_selector.is_region_allowed(region):
        logger.info(
            f"Skipping resyncing {kind} in region {region} in account {account_id} because it's not allowed"
        )
        return
    logger.info(f"Resyncing {kind} in account {account_id} in region {region}")
    next_token = None
    if use_get_resource_api:
        semaphore = asyncio.BoundedSemaphore(
            CloudControlThrottlingConfig.SEMAPHORE.value
        )
        rate_limiter = AsyncLimiter(
            CloudControlThrottlingConfig.MAX_RATE.value,
            CloudControlThrottlingConfig.TIME_PERIOD.value,
        )
    async with session.client("cloudcontrol") as cloudcontrol:
        while True:
            try:
                params = {
                    "TypeName": kind,
                }
                if next_token:
                    params["NextToken"] = next_token

                response = await cloudcontrol.list_resources(**params)
                next_token = response.get("NextToken")
                resources = response.get("ResourceDescriptions", [])
                if not resources:
                    break
                page_resources = []
                if use_get_resource_api:
                    async with session.client(
                        "cloudcontrol",
                        config=Boto3Config(
                            retries={
                                "max_attempts": CloudControlThrottlingConfig.MAX_RETRY_ATTEMPTS.value,
                                "mode": CloudControlThrottlingConfig.RETRY_MODE.value,
                            },
                        ),
                    ) as cloudcontrol_get_resource_client:
                        resources = await asyncio.gather(
                            *(
                                describe_single_resource_cloudcontrol(
                                    kind,
                                    instance.get("Identifier"),
                                    client=cloudcontrol_get_resource_client,
                                    semaphore=semaphore,
                                    rate_limiter=rate_limiter,
                                )
                                for instance in resources
                            ),
                            return_exceptions=True,
                        )
                else:
                    resources = [
                        {
                            "Identifier": instance.get("Identifier"),
                            "Properties": json.loads(instance.get("Properties")),
                        }
                        for instance in resources
                    ]

                for instance in resources:
                    if isinstance(instance, Exception):
                        if is_resource_not_found_exception(instance):
                            error = typing.cast(ClientError, instance)
                            logger.info(
                                f"Skipping resyncing {kind} resource in region {region} in account {account_id}; {error.response['Error']['Message']}"
                            )
                            continue

                        raise instance

                    serialized = instance.copy()
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
                    f"Fetched batch of {len(page_resources)} from {kind} in region {region}"
                )
                yield page_resources

                if not next_token:
                    break
            except Exception as e:
                if is_access_denied_exception(e):
                    logger.warning(
                        f"Skipping resyncing {kind} in region {region} in account {account_id} due to missing access permissions"
                    )
                else:
                    logger.error(f"Error resyncing {kind} in region {region}, {e}")
                raise e
