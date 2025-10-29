from typing import Any, AsyncGenerator, Callable
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from harbor.constants import DEFAULT_PAGE_SIZE, ObjectKind
from harbor.client.client_initializer import get_harbor_client
from harbor.webhooks.processors.artifact_processor import ArtifactWebhookProcessor
from harbor.webhooks.processors.project_processor import ProjectWebhookProcessor
from harbor.webhooks.processors.repository_processor import RepositoryWebhookProcessor
from harbor.webhooks.orchestrator import HarborWebhookOrchestrator


def build_params(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build API request parameters from event context and extras.

    Args:
        extra: Additional parameters to merge into the request

    Returns:
        Dictionary of request parameters including pagination and query filters
    """
    params = {"page_size": DEFAULT_PAGE_SIZE}

    if extra:
        params.update(extra)

    resource_config = event.resource_config
    selector = resource_config.selector if resource_config else None

    if selector and hasattr(selector, "query") and selector.query and selector.query != "true":
        params["q"] = selector.query

    logger.debug(
        "Built API request parameters",
        extra={
            "component": "main",
            "operation": "build_params",
            "page_size": params.get("page_size"),
            "has_query": "q" in params,
            "param_count": len(params)
        }
    )

    return params

async def resync_entity(
    fetch_method: Callable[[dict[str, Any]], AsyncGenerator[list[dict[str, Any]], None]],
    entity_type: str,
    extra_params: dict[str, Any] | None = None,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Generic resync handler for any Harbor entities.
    
    Args:
        fetch_method: Async generator method to fetch entities
        entity_type: Type of entity being resynced
        extra_params: Additional parameters for the fetch
        
    Yields:
        Batches of entities
    """
    params = build_params(extra_params)

    logger.info(
        "Starting entity resync",
        extra={
            "component": "main",
            "operation": "resync_entity",
            "entity_type": entity_type,
            "params": params
        }
    )

    total_count = 0
    batch_count = 0

    try:
        async for batch in fetch_method(params):
            batch_size = len(batch)
            total_count += batch_size
            batch_count += 1

            logger.debug(
                "Yielding entity batch",
                extra={
                    "component": "main",
                    "operation": "resync_entity",
                    "entity_type": entity_type,
                    "batch_number": batch_count,
                    "batch_size": batch_size,
                    "total_count": total_count
                }
            )
            yield batch

        logger.info(
            "Entity resync completed successfully",
            extra={
                "component": "main",
                "operation": "resync_entity",
                "entity_type": entity_type,
                "total_count": total_count,
                "batch_count": batch_count,
                "status": "success"
            }
        )
    except Exception as e:
        logger.error(
            "Failed to resync entity",
            extra={
                "component": "main",
                "operation": "resync_entity",
                "entity_type": entity_type,
                "total_count": total_count,
                "batch_count": batch_count,
                "error": str(e),
                "error_type": type(e).__name__,
                "status": "failed"
            }
        )
        raise


@ocean.on_resync(ObjectKind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Harbor projects.
    
    Args:
        kind: Entity kind (ObjectKind.PROJECT)
        
    Yields:
        Batches of projects
    """
    logger.info(
        "Starting projects resync",
        extra={
            "component": "main",
            "operation": "resync_projects",
            "kind": kind
        }
    )

    client = get_harbor_client()
    async for batch in resync_entity(client.get_paginated_projects, "projects"):
        yield batch


@ocean.on_resync(ObjectKind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Harbor users.
    
    Args:
        kind: Entity kind (ObjectKind.USER)
        
    Yields:
        Batches of users
    """
    logger.info(
        "Starting users resync",
        extra={
            "component": "main",
            "operation": "resync_users",
            "kind": kind
        }
    )

    client = get_harbor_client()
    async for batch in resync_entity(client.get_paginated_users, "users"):
        yield batch


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Harbor repositories.
    
    Args:
        kind: Entity kind (ObjectKind.REPOSITORY)
        
    Yields:
        Batches of repositories
    """
    logger.info(
        "Starting repositories resync",
        extra={
            "component": "main",
            "operation": "resync_repositories",
            "kind": kind
        }
    )

    client = get_harbor_client()
    async for batch in resync_entity(client.get_all_repositories, "repositories"):
        yield batch


@ocean.on_resync(ObjectKind.ARTIFACT)
async def resync_artifacts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Harbor artifacts with tags and scan results.
    
    Args:
        kind: Entity kind (ObjectKind.ARTIFACT)
        
    Yields:
        Batches of artifacts
    """
    logger.info(
        "Starting artifacts resync",
        extra={
            "component": "main",
            "operation": "resync_artifacts",
            "kind": kind,
            "with_tag": True,
            "with_scan_overview": True
        }
    )

    client = get_harbor_client()
    async for batch in resync_entity(
        client.get_all_artifacts,
        "artifacts",
        extra_params={"with_tag": True, "with_scan_overview": True},
    ):
        yield batch


@ocean.on_start()
async def on_start() -> None:
    """Initialize Harbor integration and configure webhooks."""
    logger.info(
        "Starting Harbor → Port Ocean Integration",
        extra={
            "component": "main",
            "operation": "on_start"
        }
    )

    try:
        client = get_harbor_client()

        logger.info(
            "Validating Harbor connection",
            extra={
                "component": "main",
                "operation": "on_start",
                "step": "validate_connection"
            }
        )
        await client.validate_connection()

        logger.info(
            "Harbor connection validated successfully",
            extra={
                "component": "main",
                "operation": "on_start",
                "step": "validate_connection",
                "status": "success"
            }
        )

        app_host = ocean.integration_config.get("app_host")

        if app_host:
            logger.info(
                "Setting up Harbor webhooks for real-time events",
                extra={
                    "component": "main",
                    "operation": "on_start",
                    "step": "setup_webhooks",
                    "app_host": str(app_host)
                }
            )

            orchestrator = HarborWebhookOrchestrator(client)
            results = await orchestrator.setup_webhooks_for_integration(
                app_host=str(app_host),
                integration_identifier=ocean.config.integration.identifier
            )

            logger.info(
                "Webhook setup completed",
                extra={
                    "component": "main",
                    "operation": "on_start",
                    "step": "setup_webhooks",
                    "total_projects": results.get("total_projects", 0),
                    "successful": results["successful"],
                    "failed": results["failed"],
                    "skipped": results["skipped"],
                    "status": "completed"
                }
            )

            if results["failed"] > 0:
                logger.warning(
                    "Some webhooks failed to create",
                    extra={
                        "component": "main",
                        "operation": "on_start",
                        "step": "setup_webhooks",
                        "failed_count": results["failed"],
                        "details_count": len(results.get("details", []))
                    }
                )
        else:
            logger.warning(
                "No app_host configured - webhooks disabled",
                extra={
                    "component": "main",
                    "operation": "on_start",
                    "step": "setup_webhooks",
                    "reason": "no_app_host",
                    "impact": "real_time_events_unavailable"
                }
            )

        logger.info(
            "Harbor → Port Ocean Integration started successfully",
            extra={
                "component": "main",
                "operation": "on_start",
                "status": "success"
            }
        )

    except ValueError as e:
        logger.error(
            "Configuration error during integration start",
            extra={
                "component": "main",
                "operation": "on_start",
                "error": str(e),
                "error_type": "ValueError",
                "status": "failed"
            }
        )
        raise
    except Exception as e:
        logger.error(
            "Failed to start Harbor integration",
            extra={
                "component": "main",
                "operation": "on_start",
                "error": str(e),
                "error_type": type(e).__name__,
                "status": "failed"
            }
        )
        raise

logger.info(
    "Registering webhook processors",
    extra={
        "component": "main",
        "operation": "register_processors",
        "processor_count": 3
    }
)

ocean.add_webhook_processor("/webhook", ArtifactWebhookProcessor)
ocean.add_webhook_processor("/webhook", ProjectWebhookProcessor)
ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)

logger.debug(
    "Webhook processors registered successfully",
    extra={
        "component": "main",
        "operation": "register_processors",
        "processors": [
            "ArtifactWebhookProcessor",
            "ProjectWebhookProcessor",
            "RepositoryWebhookProcessor"
        ],
        "status": "success"
    }
)
