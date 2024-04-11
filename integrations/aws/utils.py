import enum
import json
from typing import Any, AsyncIterator
import typing
import boto3
from loguru import logger
from overrides import AWSPortAppConfig
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from starlette.requests import Request

from port_ocean.core.handlers.port_app_config.models import ResourceConfig

ASYNC_GENERATOR_RESYNC_TYPE = AsyncIterator[list[dict[Any, Any]]]

class ResourceKindsWithSpecialHandling(enum.StrEnum):
    """
    Resource kinds with special handling
    These resource kinds are handled separately from the other resource kinds
    """

    CLOUDRESOURCE = "cloudresource"
    EC2 = "AWS::EC2::Instance"
    CLOUDFORMATION = "AWS::CloudFormation::Stack"
    LOADBALANCER = "loadbalancer"
    ELASTICACHE = "elasticache"
    ACM = "acm"

def _get_sessions(custom_aws_regions = []) -> list[boto3.Session]:
    """
    Gets boto3 sessions for the AWS regions
    """
    aws_access_key_id = ocean.integration_config.get("aws_access_key_id")
    aws_secret_access_key = ocean.integration_config.get("aws_secret_access_key")
    aws_regions = ocean.integration_config.get("aws_regions")

    aws_sessions = []
    if len(custom_aws_regions) > 0:
        for aws_region in custom_aws_regions:
            aws_sessions.append(boto3.Session(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key, region_name=aws_region))
        return aws_sessions
    
    for aws_region in aws_regions:
        aws_sessions.append(boto3.Session(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key, region_name=aws_region))
    
    return aws_sessions

def _fix_unserializable_date_properties(obj: Any) -> Any:
    """
    Handles unserializable date properties in the JSON by turning them into a string
    """
    return json.loads(json.dumps(obj, default=str))

def describe_single_resource(kind: str, identifier: str, region: str) -> dict[str, Any]:
    """
    Describes a single resource using the CloudControl API.
    """
    sessions = _get_sessions([region] if region else [])
    for session in sessions:
        region = session.region_name
        try:
            if kind == ResourceKindsWithSpecialHandling.ACM:
                acm = session.client('acm')
                response = acm.describe_certificate(CertificateArn=identifier)
                return response.get('Certificate', {})
            
            elif kind == ResourceKindsWithSpecialHandling.ELASTICACHE:
                elasticache = session.client('elasticache')
                response = elasticache.describe_cache_clusters(CacheClusterId=identifier)
                return response.get('CacheClusters', [])[0]
            
            elif kind == ResourceKindsWithSpecialHandling.LOADBALANCER:
                elbv2 = session.client('elbv2')
                response = elbv2.describe_load_balancers(LoadBalancerArns=[identifier])
                return response.get('LoadBalancers', [])[0]
            
            elif kind == ResourceKindsWithSpecialHandling.CLOUDFORMATION:
                cloudformation = session.client('cloudformation')
                response = cloudformation.describe_stacks(StackName=identifier)
                return response.get('Stacks', [])[0]
            
            elif kind == ResourceKindsWithSpecialHandling.EC2:
                ec2_client = session.client('ec2')
                described_instance = ec2_client.describe_instances(InstanceIds=[identifier])
                instance_definition = described_instance["Reservations"][0]["Instances"][0]
                return instance_definition
            
            else:
                cloudcontrol = session.client('cloudcontrol')
                response = cloudcontrol.get_resource(TypeName=kind, Identifier=identifier)
                resource_description = response.get('ResourceDescription', {})
                return {
                    'Identifier': resource_description.get('Identifier', ''),
                    'Kind': kind,
                    **json.loads(resource_description.get('Properties', {}))
                }
        except Exception as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.info(f"Resource not found: {kind} {identifier}")
                return {}
            logger.error(f"Failed to describe CloudControl Instance in region: {region}; error {e}")
            break

def describe_resources(sessions: list[boto3.Session], service_name: str, describe_method: str, list_param: str, marker_param: str = "NextToken") -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Describes a list of resources in the AWS account
    """
    for session in sessions:
        region = session.region_name
        next_token = None
        while True:
            try:
                all_resources = []
                client = session.client(service_name)
                if next_token:
                    pointer_param = marker_param if marker_param == "NextToken" else "Marker"
                    response = getattr(client, describe_method)(**{pointer_param: next_token})
                else:
                    response = getattr(client, describe_method)()
                next_token = response.get(marker_param)
                for resource in response.get(list_param, []):
                    all_resources.append(_fix_unserializable_date_properties(resource))
                yield all_resources
            except Exception as e:
                logger.error(f"Failed to list resources in region: {region}; error {e}")
                break
            if not next_token:
                break


def get_matching_kinds_from_config(kind: str) -> list[ResourceConfig]:
    """
    Gets the resource configurations that match the given resource kind
    """
    matching_resource_configs = []
    for resource_config in typing.cast(AWSPortAppConfig, event.port_app_config).resources:
        if resource_config.kind == kind:
            matching_resource_configs.append(resource_config)
        elif resource_config.selector.resource_kinds and kind in resource_config.selector.resource_kinds:
            matching_resource_configs.append(resource_config)
    return matching_resource_configs

def get_resource_kinds_from_config(kind: str) -> list[str]:
    """
    Gets the `resourceKinds` property from the port_app_config that match the given resource kind
    """
    for resource_config in typing.cast(AWSPortAppConfig, event.port_app_config).resources:
        if resource_config.kind == kind and resource_config.selector.resource_kinds:
            return resource_config.selector.resource_kinds
    return []

def validate_request(request: Request) -> None:
    """
    Validates the request by checking for the presence of the API key in the request headers.
    """
    api_key = request.headers.get('x-port-aws-ocean-api-key')
    if not api_key:
        raise ValueError("API key not found in request headers")
    if not ocean.integration_config.get("aws_api_key"):
        raise ValueError("API key not found in integration config")
    if api_key != ocean.integration_config.get("aws_api_key"):
        raise ValueError("Invalid API key")