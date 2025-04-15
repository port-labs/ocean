import json
import typing
from typing import Optional, Iterable, Callable, Awaitable

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
    resync_sqs_queue,
)

from utils.aws import (
    describe_accessible_accounts,
    get_accounts,
    get_sessions,
    initialize_access_credentials,
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
)
from port_ocean.utils.async_iterators import (
    stream_async_iterators_tasks,
)

from aioboto3 import Session

import functools

RESYNC_BATCH_SIZE = 100


async def _handle_global_resource_resync(
    kind: str,
    credentials: AwsCredentials,
    allowed_regions: Optional[Iterable[str]] = None,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)

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
    credentials: AwsCredentials,
    kind: str,
    resync_func: Callable[
        [str, Session, AWSResourceConfig], ASYNC_GENERATOR_RESYNC_TYPE
    ],
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Fetch and yield batches of resources for a single AWS account.

    Args:
        credentials: AWS credentials for the account
        kind: Type of resource to resync

    Yields:
        Batches of resources

    Raises:
        ExceptionGroup: If there are errors during resync for multiple regions
    """
    errors: list[Exception] = []
    failed_regions: list[str] = []
    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)

    # Filter regions based on resource config selector
    allowed_regions = list(
        filter(
            aws_resource_config.selector.is_region_allowed, credentials.enabled_regions
        )
    )

    logger.info(
        f"Starting resync of {kind} for account {credentials.account_id} "
        f"across {len(allowed_regions)} allowed regions"
    )

    if is_global_resource(kind):
        logger.debug(
            f"Processing global resource {kind} for account {credentials.account_id}"
        )
        async for batch in _handle_global_resource_resync(
            kind, credentials, allowed_regions
        ):
            yield batch
        return

    # Process regional resources
    tasks: list[Awaitable] = []
    async for session in credentials.create_session_for_each_region(allowed_regions):
        try:
            tasks.append(resync_func(kind, session, aws_resource_config))

            if len(tasks) >= RESYNC_BATCH_SIZE:
                async for batch in _process_tasks(
                    tasks, failed_regions, errors, session.region_name
                ):
                    yield batch

        except Exception as exc:
            logger.error(
                f"Failed to complete resync for {kind} in region {session.region_name}: {exc}",
                exc_info=True,
            )
            failed_regions.append(session.region_name)
            errors.append(exc)

    # Process any remaining tasks
    if tasks:
        async for batch in _process_tasks(
            tasks, failed_regions, errors, session.region_name
        ):
            yield batch

    if errors:
        error_msg = (
            f"Failed to fetch {kind} in {len(failed_regions)} regions "
            f"for account {credentials.account_id}. "
            f"Failed regions: {', '.join(failed_regions)}"
        )
        logger.error(error_msg)
        raise ExceptionGroup(error_msg, errors)


async def _process_tasks(
    tasks: list[Awaitable],
    failed_regions: list[str],
    errors: list[Exception],
    current_region: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Helper to process a batch of tasks and handle errors."""
    try:
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch
    except Exception as exc:
        if not is_access_denied_exception(exc):
            failed_regions.append(current_region)
            errors.append(exc)
        logger.warning(
            f"Error processing batch in region {current_region}: {exc}", exc_info=True
        )
    finally:
        tasks.clear()


@ocean.on_resync()
async def resync_all(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind in iter(ResourceKindsWithSpecialHandling):
        return

    tasks = []
    async for credentials in get_accounts():
        tasks.append(
            resync_resources_for_account(credentials, kind, resync_cloudcontrol)
        )

        if len(tasks) == RESYNC_BATCH_SIZE:  # Process 10 at a time
            async for batch in stream_async_iterators_tasks(*tasks):
                yield batch
            tasks.clear()

    if tasks:  # Process any remaining tasks
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ACCOUNT)
async def resync_account(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for account in describe_accessible_accounts():
        yield [fix_unserializable_date_properties(account)]


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ELASTICACHE_CLUSTER)
async def resync_elasticache(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)

    elasticache_resync_func = functools.partial(
        resync_custom_kind,
        service_name="elasticache",
        describe_method="describe_cache_clusters",
        result_key="CacheClusters",
        pagination_token_name="Marker",
    )

    async for credentials in get_accounts():
        async for batch in resync_resources_for_account(
            credentials=credentials,
            kind=kind,
            aws_resource_config=aws_resource_config,
            resync_func=elasticache_resync_func,
        ):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ELBV2_LOAD_BALANCER)
async def resync_elv2_load_balancer(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    elbv2_resync_func = functools.partial(
        resync_custom_kind,
        service_name="elbv2",
        describe_method="describe_load_balancers",
        result_key="LoadBalancers",
        pagination_token_name="Marker",
    )

    async for credentials in get_accounts():
        async for batch in resync_resources_for_account(
            credentials=credentials,
            kind=kind,
            resync_func=elbv2_resync_func,
        ):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ACM_CERTIFICATE)
async def resync_acm(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    acm_resync_func = functools.partial(
        resync_custom_kind,
        service_name="acm",
        describe_method="list_certificates",
        result_key="CertificateSummaryList",
        pagination_token_name="NextToken",
    )

    async for credentials in get_accounts():
        async for batch in resync_resources_for_account(
            credentials=credentials,
            kind=kind,
            resync_func=acm_resync_func,
        ):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.AMI_IMAGE)
async def resync_ami(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    ami_resync_func = functools.partial(
        resync_custom_kind,
        service_name="ec2",
        describe_method="describe_images",
        result_key="Images",
        pagination_token_name="NextToken",
        extra_params={"Owners": ["self"]},
    )

    async for credentials in get_accounts():
        async for batch in resync_resources_for_account(
            credentials=credentials,
            kind=kind,
            resync_func=ami_resync_func,
        ):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.CLOUDFORMATION_STACK)
async def resync_cloudformation(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    cloudformation_resync_func = functools.partial(
        resync_custom_kind,
        service_name="cloudformation",
        describe_method="describe_stacks",
        result_key="Stacks",
        pagination_token_name="NextToken",
    )

    async for credentials in get_accounts():
        async for batch in resync_resources_for_account(
            credentials=credentials,
            kind=kind,
            resync_func=cloudformation_resync_func,
        ):
            yield


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.SQS_QUEUE)
async def resync_sqs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    async for credentials in get_accounts():
        async for batch in resync_resources_for_account(
            credentials=credentials,
            kind=kind,
            resync_func=resync_sqs_queue,
        ):
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
