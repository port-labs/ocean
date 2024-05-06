from typing import Any

from fastapi import Response, status

from port_ocean.core.models import Entity

from utils.resources import (
    batch_resources,
    describe_single_resource,
    fix_unserializable_date_properties,
    resync_cloudcontrol,
)
from utils.config import get_resource_kinds_from_config, get_matching_kinds_from_config

from utils.aws import (
    _session_manager,
    describe_accessible_accounts,
    get_sessions,
    update_available_access_credentials,
    validate_request,
)
from port_ocean.context.ocean import ocean
from loguru import logger
from starlette.requests import Request
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from utils.enums import (
    ACCOUNT_ID_PROPERTY,
    KIND_PROPERTY,
    REGION_PROPERTY,
    ResourceKindsWithSpecialHandling,
)


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
            async with (
                session.resource("ec2") as ec2,
                session.client("ec2") as ec2_client,
            ):
                async for page in ec2.instances.pages():
                    if not page:
                        continue
                    page_instances = []
                    instance_ids = [instance.id for instance in page]
                    described_instances = await ec2_client.describe_instances(
                        InstanceIds=instance_ids,
                    )
                    for reservation in described_instances["Reservations"]:
                        for instance in reservation["Instances"]:
                            instance.update(
                                {
                                    KIND_PROPERTY: kind,
                                    ACCOUNT_ID_PROPERTY: account_id,
                                    REGION_PROPERTY: region,
                                }
                            )
                            page_instances.append(
                                fix_unserializable_date_properties(instance)
                            )
                    yield page_instances
        except Exception as e:
            logger.exception(f"Failed to list EC2 Instance in region: {region}")


@ocean.router.post("/webhook")
async def webhook(request: Request, response: Response) -> dict[str, Any]:
    validation = validate_request(request)
    validation_status = validation[0]
    message = validation[1]

    if validation_status is False:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"ok": False, "message": message}

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
                response.status_code = status.HTTP_400_BAD_REQUEST
                raise ValueError(
                    "resource_type, identifier or account_id is missing in webhook body, please add them to the event `InputTemplate` https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-events-rule-inputtransformer.html"
                )

            matching_resource_configs = get_matching_kinds_from_config(resource_type)

            if not matching_resource_configs:
                response.status_code = status.HTTP_400_BAD_REQUEST
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
                    response.status_code = status.HTTP_204_NO_CONTENT
                    continue

                logger.info("Resource found in AWS, registering change in port")
                resource.update(
                    {
                        KIND_PROPERTY: resource_type,
                        ACCOUNT_ID_PROPERTY: account_id,
                        REGION_PROPERTY: region,
                    }
                )
                await ocean.register_raw(
                    resource_config.kind, [fix_unserializable_date_properties(resource)]
                )
            logger.info("Webhook processed successfully")
            response.status_code = status.HTTP_204_NO_CONTENT
            return {"ok": True}
    except Exception as e:
        logger.exception(f"Failed to process event from aws")
        if response.status_code <= 299:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"ok": False}
