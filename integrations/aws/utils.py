import enum
import json
from typing import Any, AsyncIterator, Optional
import typing
import aioboto3
from loguru import logger
from overrides import AWSPortAppConfig
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from starlette.requests import Request
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

IDENTIFIER_PROPERTY = '__Identifier'
ACCOUNT_ID_PROPERTY = '__AccountId'
KIND_PROPERTY = '__Kind'
REGION_PROPERTY = '__Region'

class ResourceKindsWithSpecialHandling(enum.StrEnum):
    """
    Resource kinds with special handling
    These resource kinds are handled separately from the other resource kinds
    """
    ACCOUNT = "AWS::Organizations::Account"
    CLOUDRESOURCE = "cloudresource"
    EC2 = "AWS::EC2::Instance"
    CLOUDFORMATION = "AWS::CloudFormation::Stack"
    LOADBALANCER = "AWS::ElasticLoadBalancingV2::LoadBalancer"
    ACM = "AWS::ACMPCA::Certificate"

class AwsCredentials:
    def __init__(self, account_id: str, access_key_id: str, secret_access_key: str, session_token: Optional[str] = None):
        self.account_id = account_id
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token
        self.enabled_regions = []
    
    async def updateEnabledRegions(self):
        session = aioboto3.Session(self.access_key_id, self.secret_access_key, self.session_token)
        async with session.client("account") as account_client:
            response = await account_client.list_regions(RegionOptStatusContains=['ENABLED', 'ENABLED_BY_DEFAULT'])
            regions = response.get("Regions", [])
            self.enabled_regions = [region["RegionName"] for region in regions]

    def isRole(self):
        return self.session_token is not None
    
    async def createSession(self, region: str) -> aioboto3.Session:
        if self.isRole():
            return aioboto3.Session(self.access_key_id, self.secret_access_key, self.session_token, region)
        else:
            return aioboto3.Session(aws_access_key_id=self.access_key_id, aws_secret_access_key=self.secret_access_key, region_name=region)
        
    async def createSessionForEachRegion(self) -> AsyncIterator[aioboto3.Session]:
        for region in self.enabled_regions:
            yield self.createSession(region)

# aws credentials for syncing resources
_aws_credentials: list[AwsCredentials] = []

# aws accessible accounts for account entity
_aws_accessible_accounts: list[dict[str, Any]] = []

def find_credentials_by_account_id(account_id: str) -> AwsCredentials:
    for cred in _aws_credentials:
        if cred.account_id == account_id:
            return cred
    raise ValueError(f"Cannot find credentials linked with this account id {account_id}")

async def find_account_id_by_session(session: aioboto3.Session) -> str:
    session_credentials = await session.get_credentials()
    for cred in _aws_credentials:
        if cred.access_key_id == session_credentials.access_key:
            return cred.account_id
    raise ValueError(f"Cannot find credentials linked with this session {session}")

async def update_available_access_credentials() -> None:
    """
    Fetches the AWS account IDs that the current IAM role can access.
    and saves them up to use as sessions
    
    :return: List of AWS account IDs.
    """
    logger.info("Updating AWS credentials")
    _aws_accessible_accounts.clear()
    _aws_credentials.clear()

    aws_access_key_id = ocean.integration_config.get("aws_access_key_id")
    aws_secret_access_key = ocean.integration_config.get("aws_secret_access_key")
    if not aws_access_key_id or not aws_secret_access_key:
        logger.error("Did not specify AWS account to use, please add aws user credentials")
        return

    user_session = aioboto3.Session(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
    async with user_session.client('sts') as sts_client:
        caller_identity = await sts_client.get_caller_identity()
        current_account_id = caller_identity['Account']
        user_credentials = AwsCredentials(
            account_id=current_account_id,
            access_key_id=aws_access_key_id,
            secret_access_key=aws_secret_access_key,
        )
        await user_credentials.updateEnabledRegions()
        _aws_credentials.append(user_credentials)

        account_read_role_name = ocean.integration_config.get("account_read_role_name")
        organization_role_arn = ocean.integration_config.get("organization_role_arn")
        if not account_read_role_name or not organization_role_arn:
            # In case the account read role name or organization role ARN is not specified, only use the current account
            _aws_accessible_accounts.append({
                'Id': current_account_id,
                'Name': 'Current Account',
            })
            logger.warning("Did not specify account read role name or organization role ARN, only using the current account.")
            logger.warning("Please specify account read role name and organization role ARN to access other accounts.")
            return
        
        organizations_client = await sts_client.assume_role(
            RoleArn=organization_role_arn,
            RoleSessionName='AssumeRoleSession'
        )

        credentials = organizations_client['Credentials']
        organization_role_session = aioboto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
        # Get the list of all AWS accounts
        async with organization_role_session.client('organizations') as organizations_client:
            paginator = organizations_client.get_paginator('list_accounts')
            try:
                async for page in paginator.paginate():
                    for account in page['Accounts']:
                        if account['Id'] == current_account_id:
                            _aws_accessible_accounts.append(account)
                            # Skipping current account {current_account_id}, since it is the caller's account.
                            continue
                        try:
                            account_role = await sts_client.assume_role(
                                RoleArn=f'arn:aws:iam::{account["Id"]}:role/{account_read_role_name}',
                                RoleSessionName='AssumeRoleSession'
                            )
                            credentials = account_role['Credentials']
                            credentials = AwsCredentials(
                                account_id=account['Id'],
                                access_key_id=credentials['AccessKeyId'],
                                secret_access_key=credentials['SecretAccessKey'],
                                session_token=credentials['SessionToken']
                            )
                            await credentials.updateEnabledRegions()
                            # Add the credentials to the list of available credentials, to use to read all resources
                            _aws_credentials.append(credentials)
                            # Add the account to the list of accessible accounts, to create account entities
                            _aws_accessible_accounts.append(account)
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
            finally:
                logger.info(f"Found {len(_aws_credentials)} AWS accounts")

def describe_accessible_accounts() -> list[dict[str, Any]]:
    return _aws_accessible_accounts

async def _get_sessions(custom_account_id: Optional[str] = None, custom_region: Optional[str] = None) -> AsyncIterator[aioboto3.Session]:
    """
    Gets boto3 sessions for the AWS regions
    """
    if custom_account_id:
        credentials = find_credentials_by_account_id(custom_account_id)
        if custom_region:
            yield await credentials.createSession(custom_region)
        else:
            async for session in credentials.createSessionForEachRegion():
                yield await session
        return
    
    
    for credentials in _aws_credentials:
        if custom_region:
            yield await credentials.createSession(custom_region)
        else:
            async for session in credentials.createSessionForEachRegion():
                yield await session

def is_global_resource(kind: str) -> bool:
    """
    Checks if the resource kind is a global resource
    """
    global_services = ['cloudfront', 'route53', 'waf', 'waf-regional', 'iam', 'organizations']
    service = kind.split('::')[1].lower()
    return service in global_services

def _fix_unserializable_date_properties(obj: Any) -> Any:
    """
    Handles unserializable date properties in the JSON by turning them into a string
    """
    return json.loads(json.dumps(obj, default=str))

async def describe_single_resource(kind: str, identifier: str, account_id: Optional[str] = None, region: Optional[str] = None) -> dict[str, Any]:
    """
    Describes a single resource using the CloudControl API.
    """
    async for session in _get_sessions(account_id, region):
        region = session.region_name
        try:
            if kind == ResourceKindsWithSpecialHandling.ACM:
                async with session.client('acm') as acm:
                    response = await acm.describe_certificate(CertificateArn=identifier)
                    return response.get('Certificate', {})
            
            elif kind == ResourceKindsWithSpecialHandling.LOADBALANCER:
                async with session.client('elbv2') as elbv2:
                    response = await elbv2.describe_load_balancers(LoadBalancerArns=[identifier])
                    return response.get('LoadBalancers', [])[0]
            
            elif kind == ResourceKindsWithSpecialHandling.CLOUDFORMATION:
                async with session.client('cloudformation') as cloudformation:
                    response = await cloudformation.describe_stacks(StackName=identifier)
                    return response.get('Stacks', [])[0]
            
            elif kind == ResourceKindsWithSpecialHandling.EC2:
                async with session.client('ec2') as ec2_client:
                    described_instance = await ec2_client.describe_instances(InstanceIds=[identifier])
                    instance_definition = described_instance["Reservations"][0]["Instances"][0]
                    return instance_definition
                
            else:
                async with session.client('cloudcontrol') as cloudcontrol:
                    response = await cloudcontrol.get_resource(TypeName=kind, Identifier=identifier)
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

async def batch_resources(kind: str, session: aioboto3.Session, service_name: str, describe_method: str, list_param: str, marker_param: str = "NextToken") -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Describes a list of resources in the AWS account
    """
    region = session.region_name
    account_id = await find_account_id_by_session(session)
    next_token = None
    while True:
        try:
            all_resources = []
            async with session.client(service_name) as client:
                if next_token:
                    pointer_param = marker_param if marker_param == "NextToken" else "Marker"
                    response = await getattr(client, describe_method)(**{pointer_param: next_token})
                else:
                    response = await getattr(client, describe_method)()
                next_token = response.get(marker_param)
                for resource in response.get(list_param, []):
                    resource.update({KIND_PROPERTY: kind, ACCOUNT_ID_PROPERTY: account_id, REGION_PROPERTY: region, IDENTIFIER_PROPERTY: resource.get('Identifier')})
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