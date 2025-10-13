"""Harbor Ocean Integration - Main Resync Implementation."""

from typing import Any
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from harbor.constants import DEFAULT_PAGE_SIZE, ObjectKind
from harbor.client.client_initializer import init_harbor_client
from harbor.webhooks.orchestrator import HarborWebhookOrchestrator


@ocean.on_resync(ObjectKind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Harbor projects."""
    client = init_harbor_client()

    # Access selector from the event context
    resource_config = event.resource_config
    selector = resource_config.selector if resource_config else None

    # Build API parameters from selector configuration
    params: dict[str, Any] = {
        "page_size": DEFAULT_PAGE_SIZE,
    }

    # Add query if it exists in selector and is not "true" (Port's default selector)
    if selector and hasattr(selector, 'query') and selector.query and selector.query != "true":
        params["q"] = selector.query

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
    """Resync Harbor users."""
    client = init_harbor_client()

    resource_config = event.resource_config
    selector = resource_config.selector if resource_config else None

    params: dict[str, Any] = {
        "page_size": DEFAULT_PAGE_SIZE,
    }

    if selector and hasattr(selector, 'query') and selector.query and selector.query != "true":
        params["q"] = selector.query

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
    """Resync Harbor repositories."""
    client = init_harbor_client()

    resource_config = event.resource_config
    selector = resource_config.selector if resource_config else None

    params: dict[str, Any] = {
        "page_size": DEFAULT_PAGE_SIZE,
    }

    if selector and hasattr(selector, 'query') and selector.query and selector.query != "true":
        params["q"] = selector.query

    logger.info(f"Starting repository resync with params: {params}")

    try:
        logger.info("Fetching repositories from all projects")
        async for repositories in client.get_all_repositories(params):
            logger.info(
                f"Received batch with {len(repositories)} repositories")
            yield repositories
    except Exception as e:
        logger.error(f"Error during repository resync: {e}")
        raise


@ocean.on_resync(ObjectKind.ARTIFACT)
async def resync_artifacts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Harbor artifacts."""
    client = init_harbor_client()

    resource_config = event.resource_config
    selector = resource_config.selector if resource_config else None

    params: dict[str, Any] = {
        "page_size": DEFAULT_PAGE_SIZE,
        "with_tag": True,
        "with_scan_overview": True,
    }

    if selector and hasattr(selector, 'query') and selector.query and selector.query != "true":
        params["q"] = selector.query

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
    """Initialize the Harbor integration on startup."""
    logger.info('''
════════════════════════════════════════════════════════════════════════════

  Harbor → Port Ocean Integration
  Status: Starting...

════════════════════════════════════════════════════════════════════════════
    ''')

    try:
        client = init_harbor_client()

        logger.info("Validating Harbor connection...")
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

            logger.info(
                f"✓ Webhook setup completed: "
                f"{results['successful']} successful, "
                f"{results['failed']} failed, "
                f"{results['skipped']} skipped"
            )

            if results['failed'] > 0:
                logger.warning(
                    f"Some webhooks failed to create. Check project permissions. "
                    f"Details: {results['details']}"
                )
        else:
            logger.warning(
                "No app_host configured - webhooks will not be set up. "
                "Real-time events will not be available."
            )

        logger.info('''
════════════════════════════════════════════════════════════════════════════

  Harbor → Port Ocean Integration
  Status: ✓ Running

════════════════════════════════════════════════════════════════════════════
        ''')

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to start Harbor integration: {e}")
        raise
