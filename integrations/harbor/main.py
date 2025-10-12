"""Harbor Ocean Integration - Main Resync Implementation.

This module implements the core resync functionality for the Harbor integration,
handling data synchronization for projects, users, repositories, and artifacts.
"""

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
    """Resync Harbor projects.

    Fetches all projects from Harbor based on the configured selector filters
    and yields them in batches to Port.

    Args:
        kind: The resource kind being resynced ("project")

    Yields:
        List of project dictionaries containing project data
    """
    client = init_harbor_client()

    # Access selector from the event context
    selector = event.resource_config.selector

    # Build API parameters from selector configuration
    params: dict[str, Any] = {
        "page_size": DEFAULT_PAGE_SIZE,
    }

    # Add query if it exists in selector and is not "true" (Port's default selector)
    if hasattr(selector, 'query') and selector.query and selector.query != "true":
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
    """Resync Harbor users.

    Fetches all users from Harbor based on the configured selector filters
    and yields them in batches to Port.

    Args:
        kind: The resource kind being resynced ("user")

    Yields:
        List of user dictionaries containing user data
    """
    client = init_harbor_client()

    # Access selector from the event context
    selector = event.resource_config.selector

    # Build API parameters from selector configuration
    params: dict[str, Any] = {
        "page_size": DEFAULT_PAGE_SIZE,
    }

    # Add query if it exists in selector and is not "true" (Port's default selector)
    if hasattr(selector, 'query') and selector.query and selector.query != "true":
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
    """Resync Harbor repositories.

    Fetches all repositories from Harbor based on the configured selector filters.

    Args:
        kind: The resource kind being resynced ("repository")

    Yields:
        List of repository dictionaries containing repository data
    """
    client = init_harbor_client()

    # Access selector from the event context
    selector = event.resource_config.selector

    # Build API parameters from selector configuration
    params: dict[str, Any] = {
        "page_size": DEFAULT_PAGE_SIZE,
    }

    # Add query if it exists in selector and is not "true" (Port's default selector)
    if hasattr(selector, 'query') and selector.query and selector.query != "true":
        params["q"] = selector.query

    logger.info(f"Starting repository resync with params: {params}")

    try:
        # Fetch repositories from all projects
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
    """Resync Harbor artifacts.

    Fetches all artifacts from Harbor based on the configured selector filters.

    Args:
        kind: The resource kind being resynced ("artifact")

    Yields:
        List of artifact dictionaries containing artifact data
    """
    client = init_harbor_client()

    # Access selector from the event context
    selector = event.resource_config.selector

    # Build API parameters from selector configuration
    params: dict[str, Any] = {
        "page_size": DEFAULT_PAGE_SIZE,
        "with_tag": True,
        "with_scan_overview": True,
    }

    # Add query if it exists in selector and is not "true" (Port's default selector)
    if hasattr(selector, 'query') and selector.query and selector.query != "true":
        params["q"] = selector.query

    logger.info(f"Starting artifact resync with params: {params}")

    try:
        # Fetch artifacts from all projects and repositories
        logger.info("Fetching artifacts from all projects")
        async for artifacts in client.get_all_artifacts(params):
            logger.info(f"Received batch with {len(artifacts)} artifacts")
            yield artifacts
    except Exception as e:
        logger.error(f"Error during artifact resync: {e}")
        raise


# ============================================================================
# Integration Initialization
# ============================================================================


@ocean.on_start()
async def on_start() -> None:
    """
    Initialize the Harbor integration on startup.

    This function:
    1. Validates Harbor connection
    2. Sets up webhooks for real-time events (if app_host available)
    3. Logs startup banner
    """
    logger.info('''
════════════════════════════════════════════════════════════════════════════

  Harbor → Port Ocean Integration
  Status: Starting...

════════════════════════════════════════════════════════════════════════════
    ''')

    try:
        # Initialize client
        client = init_harbor_client()

        # Validate connection
        logger.info("Validating Harbor connection...")
        await client.validate_connection()
        logger.info("✓ Harbor connection validated successfully")

        # Setup webhooks if app_host is available
        if ocean.app.app_host:
            logger.info("Setting up Harbor webhooks for real-time events...")

            orchestrator = HarborWebhookOrchestrator(client)
            results = await orchestrator.setup_webhooks_for_integration(
                app_host=ocean.app.app_host,
                integration_identifier=ocean.config.integration.identifier
            )

            # Log webhook setup results
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
