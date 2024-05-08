import json
import typing

from fastapi import Response, status
import fastapi
from starlette import responses
from pydantic import BaseModel

from integration import AWSResourceConfig
from port_ocean.core.models import Entity
from port_ocean.context.event import event

from utils.resources import (
    batch_resources,
    describe_single_resource,
    fix_unserializable_date_properties,
    resync_cloudcontrol,
)
from utils.config import get_matching_kinds_from_config

from utils.aws import (
    _session_manager,
    describe_accessible_accounts,
    get_sessions,
    update_available_access_credentials,
    validate_request,
)
from port_ocean.context.ocean import ocean
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from utils.misc import (
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
    resource_kinds = typing.cast(
        AWSResourceConfig, event.resource_config
    ).selector.resource_kinds
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


@ocean.app.fast_api_app.middleware("aws_cloud_event")
async def cloud_event_validation_middleware_handler(
    request: fastapi.Request,
    call_next: typing.Callable[[fastapi.Request], typing.Awaitable[responses.Response]],
) -> responses.Response:
    if request.method == "OPTIONS" and request.url.path.startswith("/integration"):
        logger.info("Detected cloud event validation request")
        headers = {
            "WebHook-Allowed-Rate": "100",
            "WebHook-Allowed-Origin": "*",
        }
        response = fastapi.Response(status_code=200, headers=headers)
        return response

    validation = validate_request(request)
    validation_status = validation[0]
    message = validation[1]
    if validation_status is False:
        return fastapi.Response(
            status_code=status.HTTP_401_UNAUTHORIZED, content=message
        )

    return await call_next(request)


class ResourceUpdate(BaseModel):
    resource_type: str
    identifier: str
    accountId: str
    awsRegion: str


@ocean.router.post("/webhook")
async def webhook(update: ResourceUpdate, response: Response) -> fastapi.Response:
    try:
        logger.info(f"Received AWS Webhook request body: {update}")
        resource_type = update.resource_type
        identifier = update.identifier
        account_id = update.accountId
        region = update.awsRegion

        with logger.contextualize(
            account_id=account_id, resource_type=resource_type, identifier=identifier
        ):
            matching_resource_configs = get_matching_kinds_from_config(resource_type)

            logger.debug(
                "Querying full resource on AWS before registering change in port"
            )
            resource = await describe_single_resource(
                resource_type, identifier, account_id, region
            )
            for resource_config in matching_resource_configs:
                if not resource:  # Resource probably deleted
                    blueprint = resource_config.port.entity.mappings.blueprint.strip(
                        '"'
                    )
                    logger.info("Resource not found in AWS, un-registering from port")
                    await ocean.unregister(
                        [
                            Entity(
                                blueprint=blueprint,
                                identifier=identifier,
                            )
                        ]
                    )
                else:  # Resource found in AWS, update port
                    logger.info("Resource found in AWS, registering change in port")
                    resource.update(
                        {
                            KIND_PROPERTY: resource_type,
                            ACCOUNT_ID_PROPERTY: account_id,
                            REGION_PROPERTY: region,
                        }
                    )
                    await ocean.register_raw(
                        resource_config.kind,
                        [fix_unserializable_date_properties(resource)],
                    )

            logger.info("Webhook processed successfully")
            return fastapi.Response(
                status_code=status.HTTP_200_OK, content=json.dumps({"ok": True})
            )
    except Exception as e:
        logger.exception("Failed to process event from aws")
        return fastapi.Response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=json.dumps({"ok": False, "error": str(e)}),
        )
