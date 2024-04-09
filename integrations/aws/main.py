import time
from typing import Any

import boto3
import json
from utils import ASYNC_GENERATOR_RESYNC_TYPE, ResourceKindsWithSpecialHandling, _describe_resources, _fix_unserializable_date_properties
from port_ocean.context.ocean import ocean
from loguru import logger
from starlette.requests import Request

def get_accessible_accounts():
    """
    Fetches the AWS account IDs that the current IAM role can access.
    
    :return: List of AWS account IDs.
    """
    sts_client = boto3.client('sts')
    caller_identity = sts_client.get_caller_identity()
    current_account_id = caller_identity['Account']
    ROLE_NAME = 'ocean-integ-poc-role'

    # Get the list of all AWS accounts
    organizations_client = boto3.client('organizations')
    paginator = organizations_client.get_paginator('list_accounts')
    accounts = []
    for page in paginator.paginate():
        for account in page['Accounts']:
            try:
                assumed_role = sts_client.assume_role(
                    RoleArn=f'arn:aws:iam::{account["Id"]}:role/{ROLE_NAME}',
                    RoleSessionName='AssumeRoleSession'
                )
                # If assume_role succeeds, add the account ID to the list
                accounts.append(account['Id'])
            except sts_client.exceptions.ClientError as e:
                # If assume_role fails due to permission issues or non-existent role, skip the account
                if e.response['Error']['Code'] == 'AccessDenied':
                    continue
                else:
                    raise
    return accounts

def format_cloudcontrol_resource(kind: str, resource: dict[str, Any]) -> dict[str, Any]:
    return {
                'Identifier': resource.get('Identifier', ''),
                'Kind': kind,
                **json.loads(resource.get('Properties', {}))
            }

def describe_single_resource(kind: str, identifier: str, region: str) -> dict[str, Any]:

    sessions = _get_sessions([region] if region else [])
    for session in sessions:
        region = session.region_name
        try:
            cloudcontrol = session.client('cloudcontrol')
            response = cloudcontrol.get_resource(TypeName=kind, Identifier=identifier)
            return format_cloudcontrol_resource(kind, response.get('ResourceDescription', {}))
        except Exception as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.info(f"Resource not found: {kind} {identifier}")
                return {}
            logger.error(f"Failed to describe CloudControl Instance in region: {region}; error {e}")
            break

def _get_sessions(custom_aws_regions = []) -> list[boto3.Session]:
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

@ocean.on_resync()
async def resync_all(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind in iter(ResourceKindsWithSpecialHandling):
        logger.info("Kind already has a specific handling, skipping", kind=kind)
        return
    async for batch in resync_cloudcontrol(kind):
        yield batch

@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.CLOUDRESOURCE)
async def resync_generic_cloud_resource(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    DEFAULT_AWS_CLOUD_CONTROL_RESOURCES = [
        "AWS::Lambda::Function",
        "AWS::RDS::DBInstance",
        "AWS::S3::Bucket",
        "AWS::IAM::User",
        "AWS::ECS::Cluster",
        "AWS::ECS::Service",
        "AWS::Logs::LogGroup",
        "AWS::DynamoDB::Table",
        "AWS::SQS::Queue",
        "AWS::SNS::Topic",
        "AWS::Cognito::IdentityPool",
        "AWS::CloudFormation::Stack"
    ]

    for kind in DEFAULT_AWS_CLOUD_CONTROL_RESOURCES:
        async for batch in resync_cloudcontrol(kind):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ACM)
async def resync_acm() -> ASYNC_GENERATOR_RESYNC_TYPE:
    sessions = _get_sessions()
    for batch in _describe_resources(sessions, 'acm', 'list_certificates', 'CertificateSummaryList', 'NextToken'):
        yield batch

@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ELASTICACHE)
async def resync_elasticache() -> ASYNC_GENERATOR_RESYNC_TYPE:
    sessions = _get_sessions()
    for batch in _describe_resources(sessions, 'elasticache', 'describe_cache_clusters', 'CacheClusters', 'NextMarker'):
        yield batch

@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.LOADBALANCER)
async def resync_loadbalancer() -> ASYNC_GENERATOR_RESYNC_TYPE:
    sessions = _get_sessions()
    for batch in _describe_resources(sessions, 'elbv2', 'describe_load_balancers', 'LoadBalancers', 'NextMarker'):
        yield batch

@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.CLOUDFORMATION)
async def resync_cloudformation() -> ASYNC_GENERATOR_RESYNC_TYPE:
    sessions = _get_sessions()
    for batch in _describe_resources(sessions, 'cloudformation', 'list_stacks', 'StackSummaries', 'NextToken'):
        yield batch


async def resync_cloudcontrol(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sessions = _get_sessions()
    next_token = None
    for session in sessions:
        region = session.region_name
        while True:
            all_instances = []
            try:
                cloudcontrol = session.client('cloudcontrol')
                params = {
                    'TypeName': kind,
                }
                if next_token:
                    params['NextToken'] = next_token
                
                response = cloudcontrol.list_resources(**params)
                next_token = response.get('NextToken')
                for instance in response.get('ResourceDescriptions', []):
                    all_instances.append({
                        'Identifier': instance.get('Identifier', ''),
                        'Kind': kind,
                        **json.loads(instance.get('Properties', {}))
                    })
                yield all_instances
            except Exception as e:
                logger.error(f"Failed to list CloudControl Instance in region: {region}; error {e}")
                break
            if not next_token:
                break
                

@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.EC2)
async def resync_ec2(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sessions = _get_sessions()
    for session in sessions:
        region = session.region_name
        try:
            ec2 = session.resource('ec2')
            ec2_client = session.client('ec2')
            for page in ec2.instances.pages():
                page_instances = []
                for instance in page:
                    described_instance = ec2_client.describe_instances(InstanceIds=[instance.id])
                    instance_definition = described_instance["Reservations"][0]["Instances"][0]
                    seriliazable_instance = _fix_unserializable_date_properties(instance_definition)
                    page_instances.append(seriliazable_instance)
                yield page_instances
        except Exception as e:
            logger.error(f"Failed to list EC2 Instance in region: {region}; error {e}")
            break


@ocean.router.post("/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    logger.info("Received webhook")
    try:
        body = await request.json()
        logger.info("Webhook body", body=body)
        resource = describe_single_resource(body.get("resource_type"), body.get("identifier"), body.get("awsRegion"))
        if not resource: # Resource probably deleted
            await ocean.unregister_raw(body.get("resource_type"), body.get("identifier"))
            return {"ok": True}
        await ocean.register_raw(body.get("resource_type"), _fix_unserializable_date_properties(resource))
    except Exception as e:
        logger.error("Failed to process event from aws", error=e)
        return {"ok": False}
    
    logger.info("Webhook processed successfully")
    return {"ok": True}

@ocean.on_start()
async def on_start() -> None:
    print("Starting integration")
        # Initialize SQS client
    # sqs = boto3.client('sqs')

    # # Queue name as defined in the CloudFormation template
    # queue_name = 'port-aws-sam-exporter-test-EventsQueue-vEbxeeDUOyFP'

    # # Get the queue URL
    # response = sqs.get_queue_url(QueueName=queue_name)
    # queue_url = response['QueueUrl']
    # await query_sqs(queue_url)

    # aws_access_key_id = ocean.integration_config.get("aws_access_key_id")
    # aws_secret_access_key = ocean.integration_config.get("aws_secret_access_key")
    # sts_client = boto3.client('sts', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
    # sts_client.get_caller_identity()
    # response = sts_client.assume_role(
    #     RoleArn="arn:aws:iam::891377315606:role/ocean-integ-poc-role",
    #     RoleSessionName="2ndSession"
    # )
    # credentials = response['Credentials']
    # assumable_roles = get_accessible_accounts()
    # print(assumable_roles)
