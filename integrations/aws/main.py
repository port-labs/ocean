import json
from typing import Any

import boto3
from port_ocean.core.models import Entity
from utils import ASYNC_GENERATOR_RESYNC_TYPE, ResourceKindsWithSpecialHandling, describe_resources, describe_single_resource, _fix_unserializable_date_properties, _get_sessions, validate_request, get_matching_kinds_from_config, get_resource_kinds_from_config
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
    try:
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
    except Exception as e:
        logger.error(f"Failed to list AWS accounts; error {e}")
    except organizations_client.exceptions.AccessDeniedException:
        # If the caller is not a member of an AWS organization, assume_role will fail with AccessDenied
        # In this case, assume the role in the current account
        logger.error("Caller is not a member of an AWS organization. Assuming role in the current account.")
        assumed_role = sts_client.assume_role(
            RoleArn=f'arn:aws:iam::{current_account_id}:role/{ROLE_NAME}',
            RoleSessionName='AssumeRoleSession'
        )
        accounts.append(current_account_id)
    return accounts


@ocean.on_resync()
async def resync_all(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind in iter(ResourceKindsWithSpecialHandling):
        logger.info("Kind already has a specific handling, skipping", kind=kind)
        return
    async for batch in resync_cloudcontrol(kind):
        yield batch

@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.CLOUDRESOURCE)
async def resync_generic_cloud_resource(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    resource_kinds = get_resource_kinds_from_config(kind)

    if len(resource_kinds) == 0:
        logger.error(f"Resource kinds not found in port app config for {kind}")
        return

    for kind in resource_kinds:
        async for batch in resync_cloudcontrol(kind):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ACM)
async def resync_acm(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sessions = _get_sessions()
    for batch in describe_resources(sessions, 'acm', 'list_certificates', 'CertificateSummaryList', 'NextToken'):
        yield batch

@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ELASTICACHE)
async def resync_elasticache(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sessions = _get_sessions()
    for batch in describe_resources(sessions, 'elasticache', 'describe_cache_clusters', 'CacheClusters', 'NextMarker'):
        yield batch

@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.LOADBALANCER)
async def resync_loadbalancer(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sessions = _get_sessions()
    for batch in describe_resources(sessions, 'elbv2', 'describe_load_balancers', 'LoadBalancers', 'NextMarker'):
        yield batch

@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.CLOUDFORMATION)
async def resync_cloudformation(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sessions = _get_sessions()
    for batch in describe_resources(sessions, 'cloudformation', 'list_stacks', 'StackSummaries', 'NextToken'):
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
                    described = describe_single_resource(kind, instance.get('Identifier'), region)
                    all_instances.append({'Kind': kind, **_fix_unserializable_date_properties(described)})
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
                    serializable_instance = _fix_unserializable_date_properties(instance_definition)
                    page_instances.append(serializable_instance)
                yield page_instances
        except Exception as e:
            logger.error(f"Failed to list EC2 Instance in region: {region}; error {e}")
            break


@ocean.router.post("/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    logger.info("Received webhook")
    validate_request(request)
    try:
        body = await request.json()
        logger.info("Webhook body", body=body)
        resource_type = body.get("resource_type")
        identifier = body.get("identifier")
        if not resource_type or not identifier:
            raise ValueError("Resource type or Identifier was not found in webhook body")
        
        matching_resource_configs = get_matching_kinds_from_config(resource_type)
        
        if not matching_resource_configs:
            raise ValueError(
                "Resource type not found in port app config, update port app config to include the resource type",
                resource_type=resource_type,
            )
        
        for resource_config in matching_resource_configs:
            blueprint = resource_config.port.entity.mappings.blueprint.strip('"')
            logger.debug(
                "Querying full resource",
                id=identifier,
                kind=resource_type,
                blueprint=blueprint,
            )
            resource = describe_single_resource(resource_type, identifier, body.get("awsRegion"))
            if not resource: # Resource probably deleted
                logger.info(
                    "Resource not found in AWS, un-registering from port",
                    id=identifier,
                    kind=resource_type,
                    blueprint=blueprint,
                )
                await ocean.unregister(
                    [
                        Entity(
                            blueprint=blueprint,
                            identifier=identifier,
                        )
                    ]
                )
                return {"ok": True}
            
            logger.info(
                "Resource found in AWS, upserting port",
                id=identifier,
                kind=resource_type,
                blueprint=blueprint,
            )
            await ocean.register_raw(resource_config.kind, _fix_unserializable_date_properties(resource))
        logger.info("Webhook processed successfully")
        return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to process event from aws error: {e}", error=e)
        return {"ok": False}

@ocean.on_start()
async def on_start() -> None:
    print("Starting integration")
    # accessible_accounts = get_accessible_accounts()
    # logger.info("Accessible accounts", accounts=accessible_accounts)
