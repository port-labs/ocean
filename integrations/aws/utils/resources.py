import asyncio
import json
from typing import Any, Literal
import typing

import aioboto3
from loguru import logger
from port_ocean.context.event import event
from utils.misc import (
    CustomProperties,
    ResourceKindsWithSpecialHandling,
    is_access_denied_exception,
)
from utils.aws import get_sessions

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from utils.aws import _session_manager, update_available_access_credentials
from utils.overrides import AWSResourceConfig
from botocore.config import Config as Boto3Config


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
                        retries={"max_attempts": 10, "mode": "standard"},
                    ),
                ) as cloudcontrol:
                    response = await cloudcontrol.get_resource(
                        TypeName=kind, Identifier=identifier
                    )
                    resource_description = response.get("ResourceDescription")
                    serialized = resource_description.copy()
                    serialized.update(
                        {
                            "Properties": json.loads(
                                resource_description.get("Properties")
                            ),
                        }
                    )
                    return serialized
    return {}


async def resync_custom_kind(
    kind: str,
    session: aioboto3.Session,
    service_name: Literal["acm", "elbv2", "cloudformation", "ec2", "elasticache"],
    describe_method: str,
    list_param: str,
    marker_param: Literal["NextToken", "Marker"],
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
    if not describe_method_params:
        describe_method_params = {}
    while await update_available_access_credentials():
        async with session.client(service_name) as client:
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
                            CustomProperties.KIND: kind,
                            CustomProperties.ACCOUNT_ID: account_id,
                            CustomProperties.REGION: region,
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
    kind: str, session: aioboto3.Session
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    use_get_resource_api = typing.cast(
        AWSResourceConfig, event.resource_config
    ).selector.use_get_resource_api
    region = session.region_name
    account_id = await _session_manager.find_account_id_by_session(session)
    logger.info(f"Resyncing {kind} in account {account_id} in region {region}")
    next_token = None
    while await update_available_access_credentials():
        async with session.client("cloudcontrol") as cloudcontrol:
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
                    resources = await asyncio.gather(
                        *(
                            describe_single_resource(
                                kind,
                                instance.get("Identifier"),
                                account_id=account_id,
                                region=region,
                            )
                            for instance in resources
                        )
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
                    serialized = instance.copy()
                    serialized.update(
                        {
                            CustomProperties.KIND: kind,
                            CustomProperties.ACCOUNT_ID: account_id,
                            CustomProperties.REGION: region,
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
                    logger.warning(f"Error resyncing {kind} in region {region}, {e}")
                raise e
