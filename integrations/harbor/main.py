from typing import Any
from loguru import logger
from fastapi import Request
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from harbor.clients import HarborClient, ProjectFilter, RepositoryFilter, ArtifactFilter
from harbor.webhooks.webhook_handler import HarborWebhookHandler
from harbor.helpers.util import get_first_tag_name, extract_scan_data
from harbor.initializer import init_harbor_client


@ocean.on_resync("project")
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    harbor_client = init_harbor_client()

    project_filter = ocean.integration_config.get("project_filter") or {}
    public = project_filter.get("visibility")
    name_prefix = project_filter.get("name_prefix")

    public_bool = None if not public or public == "all" else public == "public"

    logger.info("Starting project resync", extra={"filters": project_filter})
    count = 0

    try:
        async for project in harbor_client.get_projects(public_bool, name_prefix):
            if not isinstance(project, dict):
                continue
            count += 1
            yield [project]

        logger.info(f"Project resync complete: {count} projects synced")

    except Exception as e:
        logger.error(f"Project resync failed: {e}")
        raise


@ocean.on_resync("user")
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    harbor_client = _init_harbor_client()

    logger.info("Starting user resync")
    count = 0

    try:
        async for user in harbor_client.get_users():
            count += 1
            yield [user]

        logger.info(f"User resync complete: {count} users synced")

    except Exception as e:
        logger.error(f"User resync failed: {e}")
        raise


@ocean.on_resync("repository")
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    harbor_client = _init_harbor_client()

    project_filter_config = ocean.integration_config.get("project_filter") or {}
    repository_filter_config = ocean.integration_config.get("repository_filter") or {}

    project_filter = ProjectFilter(**project_filter_config) if project_filter_config else None
    repository_filter = RepositoryFilter(**repository_filter_config) if repository_filter_config else None

    logger.info(
        "Starting repository resync",
        extra={"filters": {"project": project_filter_config, "repository": repository_filter_config}},
    )
    count = 0

    try:
        async for project, repository in harbor_client.get_all_repositories(project_filter, repository_filter):
            count += 1
            repository["__project"] = project
            yield [repository]

        logger.info(f"Repository resync complete: {count} repositories synced")

    except Exception as e:
        logger.error(f"Repository resync failed: {e}")
        raise


@ocean.on_resync("artifact")
async def resync_artifacts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    harbor_client = _init_harbor_client()

    project_filter_config = ocean.integration_config.get("project_filter") or {}
    artifact_filter_config = ocean.integration_config.get("artifact_filter") or {}
    repository_filter_config = ocean.integration_config.get("repository_filter") or {}

    project_filter = ProjectFilter(**project_filter_config) if project_filter_config else None
    artifact_filter = ArtifactFilter(**artifact_filter_config) if artifact_filter_config else None
    repository_filter = RepositoryFilter(**repository_filter_config) if repository_filter_config else None

    logger.info(
        "Starting artifact resync",
        extra={
            "filters": {
                "project": project_filter_config,
                "artifact": artifact_filter_config,
                "repository": repository_filter_config,
            }
        },
    )
    count = 0

    try:
        async for project, repository, artifact in harbor_client.get_all_artifacts(
            project_filter, artifact_filter, repository_filter
        ):
            count += 1
            artifact["__repository"] = repository
            artifact["__project"] = project

            repo_name = repository.get("name", "") if isinstance(repository, dict) else ""
            tag_name = get_first_tag_name(artifact)
            artifact["__title"] = f"{repo_name}:{tag_name}"

            artifact["__tags"] = [t.get("name") for t in (artifact.get("tags") or []) if isinstance(t, dict)]
            artifact["__labels"] = [lb.get("name") for lb in (artifact.get("labels") or []) if isinstance(lb, dict)]

            scan_data = extract_scan_data(artifact)
            artifact.update(scan_data)

            yield [artifact]

            if count % 100 == 0:
                logger.info(f"Artifact resync progress: {count} artifacts synced")

        logger.info(f"Artifact resync complete: {count} artifacts synced")

    except Exception as e:
        logger.error(f"Artifact resync failed: {e}")
        raise


@ocean.router.post("/webhook")
async def handle_webhook_request(request: Request) -> dict[str, Any]:
    """Handle incoming Harbor webhook events."""
    body = await request.body()
    data = await request.json()

    webhook_secret = ocean.integration_config.get("webhook_secret")
    if not webhook_secret:
        logger.warning(
            "Webhook secret not configured - accepting unauthenticated requests. "
            "Set 'webhook_secret' in config to enable signature verification."
        )

    handler = HarborWebhookHandler(webhook_secret)

    signature = request.headers.get("Authorization", "")
    if not handler.verify_signature(signature, body):
        logger.warning("Webhook signature verification failed")
        return {"ok": False, "error": "Invalid signature"}

    event_type = data.get("type", "")
    event_data = data.get("event_data", {})

    logger.info("Processing webhook event", extra={"event_type": event_type, "has_event_data": bool(event_data)})

    try:
        await handler.handle_webhook_event(event_type, event_data)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}", exc_info=True)
        return {"ok": False, "error": "Internal processing error"}
