import json
import typing

from fastapi import Response, status
import fastapi
from starlette import responses
from pydantic import BaseModel

from port_ocean.core.models import Entity

from utils.resources import (
    is_global_resource,
    resync_custom_kind,
    describe_single_resource,
    fix_unserializable_date_properties,
    resync_cloudcontrol,
    resync_sqs_queue,
    resync_resource_group,
)

from utils.aws import (
    initialize_access_credentials,
    get_accounts,
    get_sessions,
    validate_request,
    get_credentials,
    get_allowed_regions,
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
    get_region_semaphore,
    get_account_semaphore,
)
from port_ocean.utils.async_iterators import (
    stream_async_iterators_tasks,
    semaphore_async_iterator,
)
import functools
from aiobotocore.session import AioSession
from aws.auth.account import RegionResolver

semaphore = get_semaphore()


async def _handle_global_resource_resync(
    kind: str,
    aws_resource_config: AWSResourceConfig,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handle global resource resync using v2 authentication."""
    session = await get_credentials().get_session(region=None)
    resolver = RegionResolver(session, aws_resource_config.selector)
    regions = list(await resolver.get_allowed_regions())
    # Note: get_sessions without account_id processes all accounts for global resources
    async for session, region in get_sessions(regions):
        try:
            async for batch in resync_cloudcontrol(
                kind, session, region, aws_resource_config
            ):
                yield batch
            return
        except Exception as e:
            if is_access_denied_exception(e):
                logger.info(
                    f"Access denied for global resource {kind} in region {region}, trying next session"
                )
                continue
            logger.error(
                f"Error processing global resource {kind} in region {region}: {e}"
            )
            raise e


async def sync_account_region_resources(
    kind: str,
    session: AioSession,
    region: str,
    aws_resource_config: AWSResourceConfig,
    account_id: str,
    errors: list[Exception],
    error_regions: list[str],
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    try:
        async for batch in resync_cloudcontrol(
            kind, session, region, aws_resource_config
        ):
            yield batch
    except Exception as exc:
        if is_access_denied_exception(exc):
            logger.info(
                f"Skipping access denied error in region {region} for account {account_id}"
            )
            return
        logger.error(f"Error in region {region} for account {account_id}: {exc}")
        errors.append(exc)
        error_regions.append(region)


async def resync_resources_for_account(
    account: dict[str, typing.Any], kind: str, aws_resource_config: AWSResourceConfig
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Fetch and yield batches of resources for a single AWS account."""
    errors: list[Exception] = []
    error_regions: list[str] = []
    account_id: str = account["Id"]

    if is_global_resource(kind):
        logger.info(f"Handling global resource {kind} for account {account_id}")
        async for batch in _handle_global_resource_resync(kind, aws_resource_config):
            yield batch
        return

    logger.info(
        f"Getting sessions for account {account_id} (parallelizing regions, limit 5)"
    )
    region_semaphore = get_region_semaphore()

    session = await get_credentials().get_session(region=None)
    resolver = RegionResolver(session, aws_resource_config.selector)
    regions = list(await resolver.get_allowed_regions())
    region_tasks = [
        semaphore_async_iterator(
            region_semaphore,
            functools.partial(
                sync_account_region_resources,
                kind,
                session,
                region,
                aws_resource_config,
                account_id,
                errors,
                error_regions,
            ),
        )
        async for session, region in get_sessions(regions, account_id=account_id)
    ]

    if region_tasks:
        async for batch in stream_async_iterators_tasks(*region_tasks):
            yield batch

    logger.info(f"Completed processing regions for account {account_id}")

    if errors:
        message = (
            f"Failed to fetch {kind} for these regions {error_regions} "
            f"with {len(errors)} errors in account {account_id}"
        )
        raise ExceptionGroup(message, errors)


@ocean.on_resync()
async def resync_all(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind in iter(ResourceKindsWithSpecialHandling):
        return

    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    account_semaphore = get_account_semaphore(limit=10)
    tasks = [
        semaphore_async_iterator(
            account_semaphore,
            functools.partial(
                resync_resources_for_account, account, kind, aws_resource_config
            ),
        )
        async for account in get_accounts()
    ]

    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ACCOUNT)
async def resync_account(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for account in get_accounts():
        yield [fix_unserializable_date_properties(account)]


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ELASTICACHE_CLUSTER)
async def resync_elasticache(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    session = await get_credentials().get_session(region=None)
    regions = await get_allowed_regions(session, aws_resource_config.selector)
    tasks = [
        semaphore_async_iterator(
            semaphore,
            functools.partial(
                resync_custom_kind,
                kind,
                session,
                region,
                "elasticache",
                "describe_cache_clusters",
                "CacheClusters",
                "Marker",
                aws_resource_config,
            ),
        )
        async for session, region in get_sessions(regions)
    ]
    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ELBV2_LOAD_BALANCER)
async def resync_elv2_load_balancer(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    session = await get_credentials().get_session(region=None)
    resolver = RegionResolver(session, aws_resource_config.selector)
    regions = list(await resolver.get_allowed_regions())
    tasks = [
        semaphore_async_iterator(
            semaphore,
            functools.partial(
                resync_custom_kind,
                kind,
                session,
                region,
                "elbv2",
                "describe_load_balancers",
                "LoadBalancers",
                "Marker",
                aws_resource_config,
            ),
        )
        async for session, region in get_sessions(regions)
    ]
    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ACM_CERTIFICATE)
async def resync_acm(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    session = await get_credentials().get_session(region=None)
    resolver = RegionResolver(session, aws_resource_config.selector)
    regions = list(await resolver.get_allowed_regions())
    tasks = [
        semaphore_async_iterator(
            semaphore,
            functools.partial(
                resync_custom_kind,
                kind,
                session,
                region,
                "acm",
                "list_certificates",
                "CertificateSummaryList",
                "NextToken",
                aws_resource_config,
            ),
        )
        async for session, region in get_sessions(regions)
    ]
    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.AMI_IMAGE)
async def resync_ami(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    session = await get_credentials().get_session(region=None)
    resolver = RegionResolver(session, aws_resource_config.selector)
    regions = list(await resolver.get_allowed_regions())
    tasks = [
        semaphore_async_iterator(
            semaphore,
            functools.partial(
                resync_custom_kind,
                kind,
                session,
                region,
                "ec2",
                "describe_images",
                "Images",
                "NextToken",
                aws_resource_config,
                {"Owners": ["self"]},
            ),
        )
        async for session, region in get_sessions(regions)
    ]
    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.CLOUDFORMATION_STACK)
async def resync_cloudformation(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    session = await get_credentials().get_session(region=None)
    resolver = RegionResolver(session, aws_resource_config.selector)
    regions = list(await resolver.get_allowed_regions())
    tasks = [
        semaphore_async_iterator(
            semaphore,
            functools.partial(
                resync_custom_kind,
                kind,
                session,
                region,
                "cloudformation",
                "describe_stacks",
                "Stacks",
                "NextToken",
                aws_resource_config,
            ),
        )
        async for session, region in get_sessions(regions)
    ]
    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.SQS_QUEUE)
async def resync_sqs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    session = await get_credentials().get_session(region=None)
    resolver = RegionResolver(session, aws_resource_config.selector)
    regions = list(await resolver.get_allowed_regions())
    tasks = [
        semaphore_async_iterator(
            semaphore,
            functools.partial(
                resync_sqs_queue,
                kind,
                session,
                region,
                aws_resource_config,
            ),
        )
        async for session, region in get_sessions(regions)
    ]
    if tasks:
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.RESOURCE_GROUP)
async def resync_resource_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    session = await get_credentials().get_session(region=None)
    resolver = RegionResolver(session, aws_resource_config.selector)
    regions = list(await resolver.get_allowed_regions())
    use_group_api = aws_resource_config.selector.list_group_resources
    if use_group_api:
        logger.info("Resyncing resource groups with resource groups api")
        resync_func = functools.partial(
            resync_resource_group,
            kind,
        )
    else:
        logger.info("Resyncing resource groups with cloudcontrol")
        resync_func = functools.partial(
            resync_cloudcontrol,
            kind,
        )

    tasks = [
        semaphore_async_iterator(
            semaphore,
            functools.partial(
                resync_func,
                session,
                region,
            ),
        )
        async for session, region in get_sessions(regions)
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
                aws_resource_config = typing.cast(
                    AWSResourceConfig, event.resource_config
                )

                resource = await describe_single_resource(
                    resource_type, identifier, aws_resource_config, account_id, region
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
                logger.debug(
                    f"Failed to describe resource {resource_type} with ID {identifier} in {region} for account {account_id}: {e}"
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


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean AWS integration")

    if not ocean.integration_config.get("live_events_api_key"):
        logger.warning(
            "No live events api key provided"
            "Without setting up the webhook, the integration will not export live changes from AWS"
        )

    await initialize_access_credentials()
