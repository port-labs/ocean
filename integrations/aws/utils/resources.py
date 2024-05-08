import json
from typing import Any, Literal

import aioboto3
from loguru import logger
from utils.misc import (
    ACCOUNT_ID_PROPERTY,
    KIND_PROPERTY,
    REGION_PROPERTY,
    ResourceKindsWithSpecialHandling,
)
from utils.aws import get_sessions
from botocore.exceptions import ClientError

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from utils.aws import _session_manager


def is_global_resource(kind: str) -> bool:
    global_services = [
        "cloudfront",
        "route53",
        "waf",
        "waf-regional",
        "iam",
        "organizations",
    ]
    service = kind.split("::")[1].lower()
    return service in global_services


def fix_unserializable_date_properties(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))


async def describe_single_resource(
    kind: str, identifier: str, account_id: str | None = None, region: str | None = None
) -> dict[str, str]:
    async for session in get_sessions(account_id, region):
        region = session.region_name
        match kind:
            case ResourceKindsWithSpecialHandling.ACM:
                async with session.client("acm") as acm:
                    response = await acm.describe_certificate(CertificateArn=identifier)
                    return response.get("Certificate")

            case ResourceKindsWithSpecialHandling.LOADBALANCER:
                async with session.client("elbv2") as elbv2:
                    response = await elbv2.describe_load_balancers(
                        LoadBalancerArns=[identifier]
                    )
                    return response.get("LoadBalancers")[0]

            case ResourceKindsWithSpecialHandling.CLOUDFORMATION:
                async with session.client("cloudformation") as cloudformation:
                    response = await cloudformation.describe_stacks(
                        StackName=identifier
                    )
                    return response.get("Stacks")[0]

            case ResourceKindsWithSpecialHandling.EC2:
                async with session.client("ec2") as ec2_client:
                    described_instance = await ec2_client.describe_instances(
                        InstanceIds=[identifier]
                    )
                    instance_definition = described_instance["Reservations"][0][
                        "Instances"
                    ][0]
                    return instance_definition

            case _:
                async with session.client("cloudcontrol") as cloudcontrol:
                    response = await cloudcontrol.get_resource(
                        TypeName=kind, Identifier=identifier
                    )
                    resource_description = response.get("ResourceDescription")
                    return {
                        "Identifier": resource_description.get("Identifier"),
                        **json.loads(resource_description.get("Properties", {})),
                    }
    return {}


async def batch_resources(
    kind: str,
    session: aioboto3.Session,
    service_name: Literal["acm", "elbv2", "cloudformation"],
    describe_method: str,
    list_param: str,
    marker_param: str = "NextToken",
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    region = session.region_name
    account_id = await _session_manager.find_account_id_by_session(session)
    next_token = None
    while True:
        try:
            async with session.client(service_name) as client:
                params: dict[str, Any] = {}
                if next_token:
                    pointer_param = (
                        marker_param if marker_param == "NextToken" else "Marker"
                    )
                    params[pointer_param] = next_token
                response = await getattr(client, describe_method)(**params)
                next_token = response.get(marker_param)
                if results := response.get(list_param, []):
                    yield [
                        {
                            **fix_unserializable_date_properties(resource),
                            **{
                                KIND_PROPERTY: kind,
                                ACCOUNT_ID_PROPERTY: account_id,
                                REGION_PROPERTY: region,
                            },
                        }
                        for resource in results
                    ]
        except Exception as e:
            logger.error(f"Failed to list resources in region: {region}; error {e}")
            break
        if not next_token:
            break


async def resync_cloudcontrol(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    is_global = is_global_resource(kind)
    async for session in get_sessions(None, None, is_global):
        region = session.region_name
        logger.info(f"Resyncing {kind} in region {region}")
        account_id = await _session_manager.find_account_id_by_session(session)
        next_token = None
        while True:
            try:
                async with session.client("cloudcontrol") as cloudcontrol:
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
                    for instance in resources:
                        described = {
                            "Identifier": instance.get("Identifier"),
                            **json.loads(instance.get("Properties", {})),
                        }
                        described.update(
                            {
                                KIND_PROPERTY: kind,
                                ACCOUNT_ID_PROPERTY: account_id,
                                REGION_PROPERTY: region,
                            }
                        )
                        page_resources.append(
                            fix_unserializable_date_properties(described)
                        )
                    yield page_resources
            except Exception:
                logger.exception(
                    f"Failed to list CloudControl Instance in account {account_id} kind {kind} region: {region}"
                )
                break
            if not next_token:
                break
