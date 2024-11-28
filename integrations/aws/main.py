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
    get_sessions,
    update_available_access_credentials,
    validate_request,
)
from port_ocean.context.ocean import ocean
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.event import event
from utils.overrides import AWSPortAppConfig, AWSResourceConfig
from utils.misc import (
    get_matching_kinds_and_blueprints_from_config,
    CustomProperties,
    ResourceKindsWithSpecialHandling,
    is_access_denied_exception,
    is_server_error,
    get_semaphore,
)
from port_ocean.utils.async_iterators import (
    stream_async_iterators_tasks,
    semaphore_async_iterator,
)
import functools

semaphore = get_semaphore()


async def _handle_global_resource_resync(
    kind: str,
    credentials: AwsCredentials,
    aws_resource_config: AWSResourceConfig,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)

    allowed_regions = filter(
        aws_resource_config.selector.is_region_allowed, credentials.enabled_regions
    )
    async for session in credentials.create_session_for_each_region(allowed_regions):
        try:
            async for batch in resync_cloudcontrol(kind, session, aws_resource_config):
                yield batch
            return
        except Exception as e:
            if is_access_denied_exception(e):
                continue
            else:
                raise e


async def resync_resources_for_account(
    credentials: AwsCredentials, kind: str
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Function to handle fetching resources for a single account."""
    errors, regions = [], []

    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)

    if is_global_resource(kind):
        async for batch in _handle_global_resource_resync(
            kind, credentials, aws_resource_config
        ):
            yield batch
    else:
        async for session in credentials.create_session_for_each_region():
            try:
                async for batch in resync_cloudcontrol(
                    kind, session, aws_resource_config
                ):
                    yield batch
            except Exception as exc:
                if is_access_denied_exception(
                    exc
                ):  # skip access denied errors since we do not want to skip deleting resources from port
                    continue
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
        semaphore_async_iterator(
            semaphore,
            functools.partial(resync_resources_for_account, credentials, kind),
        )
        async for credentials in get_accounts()
    ]
    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            await update_available_access_credentials()
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ACCOUNT)
async def resync_account(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    await update_available_access_credentials()
    for account in describe_accessible_accounts():
        yield [fix_unserializable_date_properties(account)]


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ELASTICACHE_CLUSTER)
async def resync_elasticache(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    await update_available_access_credentials()
    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)

    tasks = [
        semaphore_async_iterator(
            semaphore,
            functools.partial(
                resync_custom_kind,
                kind,
                session,
                "elasticache",
                "describe_cache_clusters",
                "CacheClusters",
                "Marker",
                aws_resource_config,
            ),
        )
        async for session in get_sessions()
    ]
    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            await update_available_access_credentials()
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ELBV2_LOAD_BALANCER)
async def resync_elv2_load_balancer(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    await update_available_access_credentials()

    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    tasks = [
        semaphore_async_iterator(
            semaphore,
            functools.partial(
                resync_custom_kind,
                kind,
                session,
                "elbv2",
                "describe_load_balancers",
                "LoadBalancers",
                "Marker",
                aws_resource_config,
            ),
        )
        async for session in get_sessions()
    ]

    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            await update_available_access_credentials()
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ACM_CERTIFICATE)
async def resync_acm(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    await update_available_access_credentials()

    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    tasks = [
        semaphore_async_iterator(
            semaphore,
            functools.partial(
                resync_custom_kind,
                kind,
                session,
                "acm",
                "list_certificates",
                "CertificateSummaryList",
                "NextToken",
                aws_resource_config,
            ),
        )
        async for session in get_sessions()
    ]

    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            await update_available_access_credentials()
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.AMI_IMAGE)
async def resync_ami(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    await update_available_access_credentials()

    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    tasks = [
        semaphore_async_iterator(
            semaphore,
            functools.partial(
                resync_custom_kind,
                kind,
                session,
                "ec2",
                "describe_images",
                "Images",
                "NextToken",
                aws_resource_config,
                {"Owners": ["self"]},
            ),
        )
        async for session in get_sessions()
    ]
    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            await update_available_access_credentials()
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.CLOUDFORMATION_STACK)
async def resync_cloudformation(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    await update_available_access_credentials()

    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    tasks = [
        semaphore_async_iterator(
            semaphore,
            functools.partial(
                resync_custom_kind,
                kind,
                session,
                "cloudformation",
                "describe_stacks",
                "Stacks",
                "NextToken",
                aws_resource_config,
            ),
        )
        async for session in get_sessions()
    ]

    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            await update_available_access_credentials()
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
            aws_port_app_config = typing.cast(AWSPortAppConfig, event.port_app_config)
            if not isinstance(aws_port_app_config, AWSPortAppConfig):
                logger.info("No resources configured in the port app config")
                return fastapi.Response(status_code=status.HTTP_200_OK)

            allowed_configs, disallowed_configs = (
                get_matching_kinds_and_blueprints_from_config(
                    resource_type, region, aws_port_app_config.resources
                )
            )

            if disallowed_configs:
                logger.info(
                    f"Unregistering resource {identifier} of type {resource_type} in region {region} and account {account_id} for blueprint {disallowed_configs.values()} because it is not allowed"
                )
                await ocean.unregister(
                    [
                        Entity(blueprint=blueprint, identifier=identifier)
                        for blueprints in disallowed_configs.values()
                        for blueprint in blueprints
                    ]
                )

            if not allowed_configs:
                logger.info(
                    f"{resource_type} not found or disabled for region {region} in account {account_id}"
                )
                return fastapi.Response(status_code=status.HTTP_200_OK)

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
                    return fastapi.Response(status_code=status.HTTP_200_OK)
                if is_server_error(e):
                    logger.error(
                        f"Cannot sync {resource_type} in region {region} in account {account_id} due to server error {e}"
                    )
                    return fastapi.Response(status_code=status.HTTP_200_OK)

                logger.error(
                    f"Failed to retrieve '{resource_type}' resource with ID '{identifier}' in region '{region}' for account '{account_id}'. "
                    f"Verify that the resource exists and that the necessary permissions are granted."
                )

                resource = None

            for kind, blueprints in allowed_configs.items():
                if not resource:  # Resource probably deleted
                    logger.info("Resource not found in AWS, un-registering from port")
                    await ocean.unregister(
                        [
                            Entity(blueprint=blueprint, identifier=identifier)
                            for blueprint in blueprints
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
                        kind, [fix_unserializable_date_properties(resource)]
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
