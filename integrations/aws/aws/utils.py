import enum
import json
from typing import Any, AsyncIterator, Literal, Optional
import typing
import aioboto3
from loguru import logger
from aws.session_manager import SessionManager
from overrides import AWSPortAppConfig, AWSResourceConfig
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from starlette.requests import Request
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from botocore.exceptions import ClientError

IDENTIFIER_PROPERTY = "__Identifier"
ACCOUNT_ID_PROPERTY = "__AccountId"
KIND_PROPERTY = "__Kind"
REGION_PROPERTY = "__Region"


class ResourceKindsWithSpecialHandling(enum.StrEnum):
    """
    Resource kinds with special handling
    These resource kinds are handled separately from the other resource kinds
    """

    ACCOUNT = "AWS::Organizations::Account"
    CLOUDRESOURCE = "cloudResource"
    EC2 = "AWS::EC2::Instance"
    CLOUDFORMATION = "AWS::CloudFormation::Stack"
    LOADBALANCER = "AWS::ElasticLoadBalancingV2::LoadBalancer"
    ACM = "AWS::ACMPCA::Certificate"


_session_manager: SessionManager = SessionManager()


async def update_available_access_credentials() -> None:
    """
    Fetches the AWS account IDs that the current IAM role can access.
    and saves them up to use as sessions

    :return: List of AWS account IDs.
    """
    logger.info("Updating AWS credentials")
    await _session_manager.reset()


def describe_accessible_accounts() -> list[dict[str, Any]]:
    return _session_manager._aws_accessible_accounts


async def get_sessions(
    custom_account_id: Optional[str] = None,
    custom_region: Optional[str] = None,
    use_default_region: Optional[bool] = None,
) -> AsyncIterator[aioboto3.Session]:
    """
    Gets boto3 sessions for the AWS regions
    """
    if custom_account_id:
        credentials = _session_manager.find_credentials_by_account_id(custom_account_id)
        if use_default_region:
            yield await credentials.create_session()
        elif custom_region:
            yield await credentials.create_session(custom_region)
        else:
            async for session in credentials.create_session_for_each_region():
                yield await session
        return

    for credentials in _session_manager._aws_credentials:
        if use_default_region:
            yield await credentials.create_session()
        elif custom_region:
            yield await credentials.create_session(custom_region)
        else:
            async for session in credentials.create_session_for_each_region():
                yield await session


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
        try:
            match kind:
                case ResourceKindsWithSpecialHandling.ACCOUNT:
                    async with session.client("acm") as acm:
                        response = await acm.describe_certificate(
                            CertificateArn=identifier
                        )
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
                            **json.loads(resource_description.get("Properties", {}))
                        }
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.info(f"Resource not found: {kind} {identifier}")
                return {}
            logger.error(
                f"Failed to describe CloudControl Instance in region: {region}; error {e}"
            )
            return {}
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
                                IDENTIFIER_PROPERTY: resource.get("Identifier"),
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
                        described = await describe_single_resource(
                            kind, instance.get("Identifier"), account_id, region
                        )
                        described.update(
                            {
                                KIND_PROPERTY: kind,
                                ACCOUNT_ID_PROPERTY: account_id,
                                REGION_PROPERTY: region,
                                IDENTIFIER_PROPERTY: instance.get("Identifier"),
                            }
                        )
                        page_resources.append(fix_unserializable_date_properties(described))
                    yield page_resources
            except Exception:
                logger.exception(
                    f"Failed to list CloudControl Instance in account {account_id} kind {kind} region: {region}"
                )
                break
            if not next_token:
                break


def get_matching_kinds_from_config(kind: str) -> list[ResourceConfig]:
    return list(
        filter(
            lambda resource_config: resource_config.kind == kind
            or (
                isinstance(resource_config, AWSResourceConfig)
                and kind in resource_config.selector.resource_kinds
            ),
            typing.cast(AWSPortAppConfig, event.port_app_config).resources,
        )
    )


def get_resource_kinds_from_config(kind: str) -> list[str]:
    """
    Gets the `resourceKinds` property from the port_app_config that match the given resource kind
    """
    resource_config = typing.cast(
        AWSPortAppConfig, event.resource_config
    )
    if (
        resource_config.kind == kind
        and hasattr(resource_config.selector, "resource_kinds")
        and resource_config.selector.resource_kinds
    ):
        return resource_config.selector.resource_kinds
    return []


def validate_request(request: Request) -> None:
    api_key = request.headers.get("x-port-aws-ocean-api-key")
    if not api_key:
        raise ValueError("API key not found in request headers")
    if not ocean.integration_config.get("aws_real_time_updates_requests_api_key"):
        raise ValueError("API key not found in integration config")
    if api_key != ocean.integration_config.get(
        "aws_real_time_updates_requests_api_key"
    ):
        raise ValueError("Invalid API key")
