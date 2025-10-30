from harbor.utils.helper import build_params
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from harbor.constants import ObjectKind
from harbor.client.client_initializer import get_harbor_client
from harbor.webhooks.processors.artifact_processor import ArtifactWebhookProcessor
from harbor.webhooks.processors.project_processor import ProjectWebhookProcessor
from harbor.webhooks.processors.repository_processor import RepositoryWebhookProcessor
from harbor.webhooks.orchestrator import HarborWebhookOrchestrator


@ocean.on_resync(ObjectKind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_harbor_client()
    params = build_params()
    
    logger.info(f"Starting project resync with params: {params}")
    
    try:
        async for projects in client.get_paginated_projects(params):
            logger.info(f"Received batch with {len(projects)} projects")
            yield projects
            
    except Exception as e:
        logger.error(f"Error during project resync: {e}")
        raise


@ocean.on_resync(ObjectKind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_harbor_client()
    params = build_params()

    logger.info(f"Starting user resync with params: {params}")

    try:
        async for users in client.get_paginated_users(params):
            logger.info(f"Received batch with {len(users)} users")
            yield users
            
    except Exception as e:
        logger.error(f"Error during user resync: {e}")
        raise


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_harbor_client()
    params = build_params()

    logger.info(f"Starting repository resync with params: {params}")

    try:
        logger.info("Fetching repositories from all projects")
        async for repositories in client.get_all_repositories(params):
            logger.info(f"Received batch with {len(repositories)} repositories")
            yield repositories
            
    except Exception as e:
        logger.error(f"Error during repository resync: {e}")
        raise


@ocean.on_resync(ObjectKind.ARTIFACT)
async def resync_artifacts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_harbor_client()
    params = build_params({"with_tag": True, "with_scan_overview": True})

    logger.info(f"Starting artifact resync with params: {params}")

    try:
        logger.info("Fetching artifacts from all projects")
        async for artifacts in client.get_all_artifacts(params):
            logger.info(f"Received batch with {len(artifacts)} artifacts")
            yield artifacts
            
    except Exception as e:
        logger.error(f"Error during artifact resync: {e}")
        raise


@ocean.on_start()
async def on_start() -> None:
    try:
        client = get_harbor_client()

        logger.info("Validating Harbor connection")
        await client.validate_connection()
        logger.info("✓ Harbor connection validated successfully")

        app_host = ocean.integration_config.get("app_host")

        if app_host:
            logger.info("Setting up Harbor webhooks for real-time events...")

            orchestrator = HarborWebhookOrchestrator(client)
            results = await orchestrator.setup_webhooks_for_integration(
                app_host=str(app_host),
                integration_identifier=ocean.config.integration.identifier
            )

            logger.info("Webhook setup completed")

            if results["failed"] > 0:
                logger.warning("Some webhooks failed to create")
        else:
            logger.warning("No app_host configured - webhooks disabled")

        logger.info("Harbor → Port Ocean Integration started successfully")

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
    
    except Exception as e:
        logger.error(f"Failed to start Harbor integration: {e}")
        raise

logger.info("Registering webhook processors")

ocean.add_webhook_processor("/webhook", ArtifactWebhookProcessor)
ocean.add_webhook_processor("/webhook", ProjectWebhookProcessor)
ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)

logger.debug("Webhook processors registered successfully")
