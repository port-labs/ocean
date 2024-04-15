import enum
import json
from typing import Any, AsyncIterator, Optional
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

class AwsCredentials:
    def __init__(self, account_id: str, access_key_id: str, secret_access_key: str, session_token: Optional[str] = None):
        self.account_id = account_id
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token
    
    def isRole(self):
        return self.session_token is not None
    
    def createSession(self, region: Optional[str] = None):
        if self.isRole():
            if region:
                return boto3.Session(self.access_key_id, self.secret_access_key, self.session_token, region)
            return boto3.Session(self.access_key_id, self.secret_access_key, self.session_token, region)
        else:
            if region:
                return boto3.Session(aws_access_key_id=self.access_key_id, aws_secret_access_key=self.secret_access_key, region_name=region)
            return boto3.Session(aws_access_key_id=self.access_key_id, aws_secret_access_key=self.secret_access_key)


_aws_credentials: list[AwsCredentials] = []

def find_credentials_by_account_id(account_id: str) -> AwsCredentials:
    for cred in _aws_credentials:
        if cred.account_id == account_id:
            return cred
    raise ValueError(f"Cannot find credentials linked with this account id {account_id}")

def find_account_id_by_session(session: boto3.Session) -> str:
    for cred in _aws_credentials:
        if cred.access_key_id == session.get_credentials().access_key:
            return cred.account_id
    raise ValueError(f"Cannot find credentials linked with this session {session}")

def update_available_access_credentials() -> None:
    """
    Fetches the AWS account IDs that the current IAM role can access.
    and saves them up to use as sessions
    
    :return: List of AWS account IDs.
    """
    logger.info("Updating AWS credentials")
    aws_access_key_id = ocean.integration_config.get("aws_access_key_id")
    aws_secret_access_key = ocean.integration_config.get("aws_secret_access_key")
    if not aws_access_key_id or not aws_secret_access_key:
        logger.error("Did not specify AWS account to use, please add aws user credentials")
        return
    
    sts_client = boto3.client('sts', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
    caller_identity = sts_client.get_caller_identity()
    current_account_id = caller_identity['Account']

    _aws_credentials.append(AwsCredentials(
        account_id=current_account_id,
        access_key_id=aws_access_key_id,
        secret_access_key=aws_secret_access_key,
    ))

    # TODO: change to be dynamic
    ROLE_NAME = 'ocean-integ-poc-role'
    organizations_client = sts_client.assume_role(
        # TODO: change to be dynamic
        RoleArn=f'arn:aws:iam::362207926288:role/AWS-Exporter-Ocean-POC-Organization-Role',
        RoleSessionName='AssumeRoleSession'
    )

    credentials = organizations_client['Credentials']
    # Get the list of all AWS accounts
    organizations_client = boto3.client('organizations', 
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )
    paginator = organizations_client.get_paginator('list_accounts')
    try:
        for page in paginator.paginate():
            for account in page['Accounts']:
                try:
                    account_role = sts_client.assume_role(
                        RoleArn=f'arn:aws:iam::{account["Id"]}:role/{ROLE_NAME}',
                        RoleSessionName='AssumeRoleSession'
                    )
                    credentials = account_role['Credentials']
                    _aws_credentials.append(AwsCredentials(
                        account_id=account['Id'],
                        access_key_id=credentials['AccessKeyId'],
                        secret_access_key=credentials['SecretAccessKey'],
                        session_token=credentials['SessionToken']
                    ))
                except sts_client.exceptions.ClientError as e:
                    # If assume_role fails due to permission issues or non-existent role, skip the account
                    if e.response['Error']['Code'] == 'AccessDenied':
                        continue
                    else:
                        raise
    except organizations_client.exceptions.AccessDeniedException:
        # If the caller is not a member of an AWS organization, assume_role will fail with AccessDenied
        # In this case, assume the role in the current account
        logger.error("Caller is not a member of an AWS organization. Assuming role in the current account.")

# TODO: change custom_aws_regions to custom role or something
def _get_sessions(custom_account_id: Optional[str] = None, custom_region: Optional[str] = None) -> list[boto3.Session]:
    """
    Gets boto3 sessions for the AWS regions
    """
    aws_sessions = []

    if custom_account_id:
        credentials = find_credentials_by_account_id(custom_account_id)
        return [credentials.createSession(custom_region)]
    
    
    for credentials in _aws_credentials:
        aws_sessions.append(credentials.createSession(custom_region if custom_region else None))
    
    return aws_sessions

def _fix_unserializable_date_properties(obj: Any) -> Any:
    """
    Handles unserializable date properties in the JSON by turning them into a string
    """
    return json.loads(json.dumps(obj, default=str))

def describe_single_resource(kind: str, identifier: str, account_id: Optional[str] = None, region: Optional[str] = None) -> dict[str, Any]:
    """
    Describes a single resource using the CloudControl API.
    """
    sessions = _get_sessions(account_id, region)
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