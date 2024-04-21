import json
from typing import Any

import aioboto3
from port_ocean.core.models import Entity
from utils import ACCOUNT_ID_PROPERTY, IDENTIFIER_PROPERTY, KIND_PROPERTY, REGION_PROPERTY, ResourceKindsWithSpecialHandling, _session_manager, describe_accessible_accounts, batch_resources, describe_single_resource, _fix_unserializable_date_properties, _get_sessions, get_resource_kinds_from_config, is_global_resource, update_available_access_credentials, validate_request, get_matching_kinds_from_config
from port_ocean.context.ocean import ocean
from loguru import logger
from starlette.requests import Request
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

@ocean.on_resync()
async def resync_all(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    await update_available_access_credentials()

    if kind in iter(ResourceKindsWithSpecialHandling):
        logger.info("Kind already has a specific handling, skipping", kind=kind)
        return
    async for batch in resync_cloudcontrol(kind):
        yield batch

@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ACCOUNT)
async def resync_account(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    serializable_account_accounts = []
    for account in describe_accessible_accounts():
        serializable_account_accounts.append(_fix_unserializable_date_properties(account))
    yield serializable_account_accounts

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
    async for session in _get_sessions():
        session = await session
        async for batch in batch_resources(kind, session, 'acm', 'list_certificates', 'CertificateSummaryList', 'NextToken'):
            yield batch

@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.LOADBALANCER)
async def resync_loadbalancer(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for session in _get_sessions():
        async for batch in batch_resources(kind, session, 'elbv2', 'describe_load_balancers', 'LoadBalancers', 'NextMarker'):
            yield batch

@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.CLOUDFORMATION)
async def resync_cloudformation(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for session in _get_sessions():
        async for batch in batch_resources(kind, session, 'cloudformation', 'list_stacks', 'StackSummaries', 'NextToken'):
            yield batch


async def resync_cloudcontrol(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    is_global = is_global_resource(kind)
    async for session in _get_sessions(None, None, is_global):
        region = session.region_name
        logger.info(f"Resyncing {kind} in region {region}")
        account_id = await _session_manager.find_account_id_by_session(session)
        next_token = None
        while True:
            all_instances = []
            try:
                async with session.client("cloudcontrol") as cloudcontrol:
                    params = {
                        'TypeName': kind,
                    }
                    if next_token:
                        params['NextToken'] = next_token
                    
                    response = await cloudcontrol.list_resources(**params)
                    next_token = response.get('NextToken')
                    resources = response.get('ResourceDescriptions', [])
                    if not resources:
                        break
                    for instance in response.get('ResourceDescriptions', []):
                        described = await describe_single_resource(kind, instance.get('Identifier'), account_id, region)
                        described.update({KIND_PROPERTY: kind, ACCOUNT_ID_PROPERTY: account_id, REGION_PROPERTY: region, IDENTIFIER_PROPERTY: instance.get('Identifier')})
                        all_instances.append(_fix_unserializable_date_properties(described))
                    yield all_instances
            except Exception as e:
                logger.error(f"Failed to list CloudControl Instance in account {account_id} kind {kind} region: {region}; error {e}")
                break
            if not next_token:
                break
                

@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.EC2)
async def resync_ec2(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for session in _get_sessions():
        region = session.region_name
        account_id = await _session_manager.find_account_id_by_session(session)
        try:
            async with session.resource('ec2') as ec2:
                async with session.client('ec2') as ec2_client:
                    async for page in ec2.instances.pages():
                        page_instances = []
                        for instance in page:
                            described_instance = await ec2_client.describe_instances(InstanceIds=[instance.id])
                            instance_definition = described_instance["Reservations"][0]["Instances"][0]
                            instance_definition.update({KIND_PROPERTY: kind, ACCOUNT_ID_PROPERTY: account_id, REGION_PROPERTY: region, IDENTIFIER_PROPERTY: instance.id})
                            page_instances.append(_fix_unserializable_date_properties(instance_definition))
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
        resource_type = body.get("resource_type")
        identifier = body.get("identifier")
        account_id = body.get("accountId")

        logger.info(f"Webhook body Account ID: {account_id} Type: {resource_type} Identifier: {identifier}")

        if not resource_type or not identifier or not account_id:
            raise ValueError("Resource type, Identifier or Account id was not found in webhook body")
        
        matching_resource_configs = get_matching_kinds_from_config(resource_type)
        
        if not matching_resource_configs:
            raise ValueError(
                "Resource type not found in port app config, update port app config to include the resource type",
                resource_type=resource_type,
            )
        
        logger.debug(
            "Querying full resource",
            id=identifier,
            kind=resource_type,
        )
        resource = await describe_single_resource(resource_type, identifier, account_id, body.get("awsRegion"))
        for resource_config in matching_resource_configs:
            blueprint = resource_config.port.entity.mappings.blueprint.strip('"')
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
                continue
            
            logger.info(
                "Resource found in AWS, upserting port",
                id=identifier,
                kind=resource_type,
                blueprint=blueprint,
            )
            resource.update({KIND_PROPERTY: resource_type, ACCOUNT_ID_PROPERTY: account_id, REGION_PROPERTY: body.get("awsRegion")})
            await ocean.register_raw(resource_config.kind, [_fix_unserializable_date_properties(resource)])
        logger.info("Webhook processed successfully")
        return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to process event from aws error: {e}", error=e)
        return {"ok": False}

@ocean.on_start()
async def on_start() -> None:
    print("Starting integration")
