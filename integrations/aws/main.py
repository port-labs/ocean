from typing import Any

from port_ocean.core.models import Entity
from aws.utils import (
    ACCOUNT_ID_PROPERTY,
    IDENTIFIER_PROPERTY,
    KIND_PROPERTY,
    REGION_PROPERTY,
    ResourceKindsWithSpecialHandling,
    _session_manager,
    describe_accessible_accounts,
    batch_resources,
    describe_single_resource,
    fix_unserializable_date_properties,
    get_sessions,
    get_resource_kinds_from_config,
    resync_cloudcontrol,
    update_available_access_credentials,
    validate_request,
    get_matching_kinds_from_config,
)
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
    for account in describe_accessible_accounts():
        yield fix_unserializable_date_properties(account)


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
    async for session in get_sessions():
        async for batch in batch_resources(
            kind,
            session,
            "acm",
            "list_certificates",
            "CertificateSummaryList",
            "NextToken",
        ):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.LOADBALANCER)
async def resync_loadbalancer(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for session in get_sessions():
        async for batch in batch_resources(
            kind,
            session,
            "elbv2",
            "describe_load_balancers",
            "LoadBalancers",
            "NextMarker",
        ):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.CLOUDFORMATION)
async def resync_cloudformation(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for session in get_sessions():
        async for batch in batch_resources(
            kind,
            session,
            "cloudformation",
            "list_stacks",
            "StackSummaries",
            "NextToken",
        ):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.EC2)
async def resync_ec2(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for session in get_sessions():
        region = session.region_name
        account_id = await _session_manager.find_account_id_by_session(session)
        try:
            async with session.resource("ec2") as ec2:
                async with session.client("ec2") as ec2_client:
                    async for page in ec2.instances.pages():
                        for instance in page:
                            described_instance = await ec2_client.describe_instances(
                                InstanceIds=[instance.id]
                            )
                            instance_definition = described_instance["Reservations"][0][
                                "Instances"
                            ][0]
                            instance_definition.update(
                                {
                                    KIND_PROPERTY: kind,
                                    ACCOUNT_ID_PROPERTY: account_id,
                                    REGION_PROPERTY: region,
                                    IDENTIFIER_PROPERTY: instance.id,
                                }
                            )
                            yield fix_unserializable_date_properties(
                                instance_definition
                            )
        except Exception as e:
            logger.error(f"Failed to list EC2 Instance in region: {region}; error {e}")


@ocean.router.post("/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    validate_request(request)
    try:
        body = await request.json()
        logger.info(f"Received AWS Webhook request body: {body}")
        resource_type = body.get("resource_type")
        identifier = body.get("identifier")
        account_id = body.get("accountId")
        region = body.get("awsRegion")

        with logger.contextualize(
            account_id=account_id, resource_type=resource_type, identifier=identifier
        ):
            if not resource_type or not identifier or not account_id:
                raise ValueError(
                    "Resource type, Identifier or Account id was not found in webhook body"
                )

            matching_resource_configs = get_matching_kinds_from_config(resource_type)

            if not matching_resource_configs:
                raise ValueError(
                    "Resource type not found in port app config, update port app config to include the resource type"
                )

            logger.debug("Querying full resource")
            resource = await describe_single_resource(
                resource_type, identifier, account_id, region
            )
            for resource_config in matching_resource_configs:
                blueprint = resource_config.port.entity.mappings.blueprint.strip('"')
                if not resource:  # Resource probably deleted
                    logger.info("Resource not found in AWS, un-registering from port")
                    await ocean.unregister(
                        [
                            Entity(
                                blueprint=blueprint,
                                identifier=identifier,
                            )
                        ]
                    )
                    continue

                logger.info("Resource found in AWS, registering change in port")
                resource.update(
                    {
                        KIND_PROPERTY: resource_type,
                        ACCOUNT_ID_PROPERTY: account_id,
                        REGION_PROPERTY: region,
                        IDENTIFIER_PROPERTY: identifier,
                    }
                )
                await ocean.register_raw(
                    resource_config.kind, [fix_unserializable_date_properties(resource)]
                )
            logger.info("Webhook processed successfully")
            return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to process event from aws error: {e}")
        return {"ok": False}
