from loguru import logger
from port_ocean.context.ocean import ocean
from client import LaunchDarklyClient, ObjectKind
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from webhook_processors import (
    FeatureFlagWebhookProcessor,
    EnvironmentWebhookProcessor,
    ProjectWebhookProcessor,
    AuditLogWebhookProcessor,
)


@ocean.on_resync(kind=ObjectKind.AUDITLOG)
async def on_resync_auditlog(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LaunchDarklyClient.create_from_ocean_configuration()
    async for auditlogs in client.get_paginated_resource(kind, page_size=20):
        yield auditlogs


@ocean.on_resync(kind=ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LaunchDarklyClient.create_from_ocean_configuration()
    async for projects in client.get_paginated_projects():
        logger.info(f"Received {kind} batch with {len(projects)} items")
        yield projects


# @ocean.on_resync(kind=ObjectKind.FEATURE_FLAG)
# async def on_resync_flags(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
#     client = LaunchDarklyClient.create_from_ocean_configuration()
#     async for flags in client.get_paginated_feature_flags():
#         logger.info(f"Received {kind} batch with {len(flags)} items")
#         yield flags


@ocean.on_resync(kind=ObjectKind.ENVIRONMENT)
async def on_resync_environments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LaunchDarklyClient.create_from_ocean_configuration()
    async for environments in client.get_paginated_environments():
        logger.info(f"Received {kind} batch with {len(environments)} items")
        yield environments


@ocean.on_resync(kind=ObjectKind.FEATURE_FLAG)
async def on_resync_flags(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LaunchDarklyClient.create_from_ocean_configuration()
    async for flags_batch in client.get_paginated_feature_flags():
        logger.info(f"Received {kind} batch with {len(flags_batch)} items")
        
        # Create tasks for processing flags in parallel
        tasks = []
        for flag in flags_batch:
            project_key = flag.get("__projectKey")
            if project_key:
                tasks.append(client.process_flag(flag, project_key))
            else:
                # For flags without project key, just pass them through
                tasks.append(asyncio.create_task(asyncio.sleep(0, result=flag)))
        
        # Wait for all tasks to complete
        processed_flags = await asyncio.gather(*tasks)
        yield processed_flags
        
@ocean.on_resync(kind=ObjectKind.FEATURE_FLAG_STATUS)
async def on_resync_feature_flag_statuses(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LaunchDarklyClient.create_from_ocean_configuration()
    async for feature_flag_status in client.get_paginated_feature_flag_statuses():
        logger.info(f"Received {kind} batch with {len(feature_flag_status)} items")
        yield feature_flag_status

@ocean.on_resync(kind=ObjectKind.FEATURE_FLAG_DEPENDENCY)
async def on_resync_flag_dependencies(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LaunchDarklyClient.create_from_ocean_configuration()
    async for flag_dependencies in client.get_paginated_feature_flag_dependencies():
        logger.info(f"Received {kind} batch with {len(flag_dependencies)} items")
        yield flag_dependencies


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean LaunchDarkly integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    base_url = ocean.app.base_url
    if not base_url:
        return

    client = LaunchDarklyClient.create_from_ocean_configuration()
    if client.webhook_secret:
        logger.info(
            "Received secret for authenticating incoming webhooks. Only authenticated webhooks will be synced."
        )

    await client.create_launchdarkly_webhook(base_url)


ocean.add_webhook_processor("/webhook", FeatureFlagWebhookProcessor)
ocean.add_webhook_processor("/webhook", EnvironmentWebhookProcessor)
ocean.add_webhook_processor("/webhook", ProjectWebhookProcessor)
ocean.add_webhook_processor("/webhook", AuditLogWebhookProcessor)
