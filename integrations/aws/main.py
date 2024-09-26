import json
import typing

from fastapi import Response, status
import fastapi
from starlette import responses
from pydantic import BaseModel

from aws.aws_credentials import AwsCredentials
from port_ocean.core.models import Entity

from utils.resources import (
    is_global_resource,
    resync_custom_kind,
    describe_single_resource,
    fix_unserializable_date_properties,
    resync_cloudcontrol,
)

from utils.aws import (
    describe_accessible_accounts,
    get_accounts,
    get_default_region_from_credentials,
    get_sessions,
    update_available_access_credentials,
    validate_request,
)
from port_ocean.context.ocean import ocean
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from utils.misc import (
    get_matching_kinds_and_blueprints_from_config,
    CustomProperties,
    ResourceKindsWithSpecialHandling,
    is_access_denied_exception,
    is_server_error,
    semaphore,
)
from port_ocean.utils.async_iterators import stream_async_iterators_tasks


async def _handle_global_resource_resync(
    kind: str,
    credentials: AwsCredentials,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    denied_access_to_default_region = False
    default_region = get_default_region_from_credentials(credentials)
    default_session = await credentials.create_session(default_region)
    try:
        async for batch in resync_cloudcontrol(kind, default_session):
            yield batch
    except Exception as e:
        if is_access_denied_exception(e):
            denied_access_to_default_region = True
        else:
            raise e

    if denied_access_to_default_region:
        logger.info(f"Trying to resync {kind} in all regions until success")
        async for session in credentials.create_session_for_each_region():
            try:
                async for batch in resync_cloudcontrol(kind, session):
                    yield batch
                break
            except Exception as e:
                if not is_access_denied_exception(e):
                    raise e


async def resync_resources_for_account(
    credentials: AwsCredentials, kind: str
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Function to handle fetching resources for a single account."""

    async with semaphore:  # limit the number of concurrent tasks
        errors, regions = [], []

        if is_global_resource(kind):
            async for batch in _handle_global_resource_resync(kind, credentials):
                yield batch
        else:
            async for session in credentials.create_session_for_each_region():
                try:
                    async for batch in resync_cloudcontrol(kind, session):
                        yield batch
                except Exception as exc:
                    regions.append(session.region_name)
                    errors.append(exc)
                    continue
        if errors:
            message = f"Failed to fetch {kind} for these regions {regions} with {len(errors)} errors in account {credentials.account_id}"
            raise ExceptionGroup(message, errors)


@ocean.on_resync()
async def resync_all(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind in iter(ResourceKindsWithSpecialHandling):
        return

    await update_available_access_credentials()
    tasks = [
        resync_resources_for_account(credentials, kind)
        async for credentials in get_accounts()
    ]
    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ACCOUNT)
async def resync_account(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    await update_available_access_credentials()
    for account in describe_accessible_accounts():
        yield [fix_unserializable_date_properties(account)]


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ELASTICACHE_CLUSTER)
async def resync_elasticache(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    await update_available_access_credentials()

    tasks = [
        resync_custom_kind(
            kind,
            session,
            "elasticache",
            "describe_cache_clusters",
            "CacheClusters",
            "Marker",
        )
        async for session in get_sessions()
    ]
    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ELBV2_LOAD_BALANCER)
async def resync_elv2_load_balancer(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    await update_available_access_credentials()

    tasks = [
        resync_custom_kind(
            kind,
            session,
            "elbv2",
            "describe_load_balancers",
            "LoadBalancers",
            "Marker",
        )
        async for session in get_sessions()
    ]

    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ACM_CERTIFICATE)
async def resync_acm(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    await update_available_access_credentials()

    tasks = [
        resync_custom_kind(
            kind,
            session,
            "acm",
            "list_certificates",
            "CertificateSummaryList",
            "NextToken",
        )
        async for session in get_sessions()
    ]

    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.AMI_IMAGE)
async def resync_ami(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    await update_available_access_credentials()
    tasks = [
        resync_custom_kind(
            kind,
            session,
            "ec2",
            "describe_images",
            "Images",
            "NextToken",
            {"Owners": ["self"]},
        )
        async for session in get_sessions()
    ]
    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.CLOUDFORMATION_STACK)
async def resync_cloudformation(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    await update_available_access_credentials()
    tasks = [
        resync_custom_kind(
            kind,
            session,
            "cloudformation",
            "describe_stacks",
            "Stacks",
            "NextToken",
        )
        async for session in get_sessions()
    ]

    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.app.fast_api_app.middleware("aws_cloud_event")
async def cloud_event_validation_middleware_handler(
    request: fastapi.Request,
    call_next: typing.Callable[[fastapi.Request], typing.Awaitable[responses.Response]],
) -> responses.Response:
    if request.url.path.startswith("/integration"):
        if request.method == "OPTIONS":
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
    await update_available_access_credentials()
    try:
        logger.info(f"Received AWS Webhook request body: {update}")
        resource_type = update.resource_type
        identifier = update.identifier
        account_id = update.accountId
        region = update.awsRegion

        with logger.contextualize(
            account_id=account_id, resource_type=resource_type, identifier=identifier
        ):
            matching_resource_configs = get_matching_kinds_and_blueprints_from_config(
                resource_type
            )

            logger.debug(
                "Querying full resource on AWS before registering change in port"
            )

            try:
                resource = await describe_single_resource(
                    resource_type, identifier, account_id, region
                )
            except Exception as e:
                if is_access_denied_exception(e):
                    logger.error(
                        f"Cannot sync {resource_type} in region {region} in account {account_id} due to missing access permissions {e}"
                    )
                    return fastapi.Response(
                        status_code=status.HTTP_200_OK,
                    )
                if is_server_error(e):
                    logger.error(
                        f"Cannot sync {resource_type} in region {region} in account {account_id} due to server error {e}"
                    )
                    return fastapi.Response(
                        status_code=status.HTTP_200_OK,
                    )
                resource = None

            for kind in matching_resource_configs:
                blueprints = matching_resource_configs[kind]
                if not resource:  # Resource probably deleted
                    for blueprint in blueprints:
                        logger.info(
                            "Resource not found in AWS, un-registering from port"
                        )
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
                            CustomProperties.KIND: resource_type,
                            CustomProperties.ACCOUNT_ID: account_id,
                            CustomProperties.REGION: region,
                        }
                    )
                    await ocean.register_raw(
                        kind,
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
