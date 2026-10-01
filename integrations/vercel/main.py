from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from vercel.clients.client_factory import create_vercel_client
from vercel.core.exporters import (
    DeploymentExporter,
    DomainExporter,
    ProjectExporter,
    TeamExporter,
)
from vercel.helpers.utils import ObjectKind
from vercel.webhook.webhook_processors import (
    DeploymentWebhookProcessor,
    DomainWebhookProcessor,
    ProjectWebhookProcessor,
)


@ocean.on_start()
async def on_start() -> None:
    """Log integration scope and configuration on startup."""
    cfg = ocean.integration_config
    team_id = cfg.get("teamId") or "personal account"
    logger.info(f"Vercel integration starting — scope: {team_id}")
    if not cfg.get("webhookSecret"):
        logger.warning(
            "webhookSecret is not configured. Incoming webhook payloads will NOT "
            "be signature-validated. Set webhookSecret to harden your deployment."
        )


@ocean.on_resync(ObjectKind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all teams from Vercel."""
    logger.info("Starting teams resync")
    client = create_vercel_client()
    exporter = TeamExporter(client)
    async for teams_batch in exporter.get_paginated_resources():
        yield teams_batch


@ocean.on_resync(ObjectKind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all projects from Vercel."""
    logger.info("Starting projects resync")
    client = create_vercel_client()
    exporter = ProjectExporter(client)
    async for projects_batch in exporter.get_paginated_resources():
        yield projects_batch


@ocean.on_resync(ObjectKind.DEPLOYMENT)
async def resync_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all deployments from Vercel."""
    logger.info("Starting deployments resync")
    client = create_vercel_client()
    exporter = DeploymentExporter(client)
    async for deployments_batch in exporter.get_paginated_resources():
        yield deployments_batch


@ocean.on_resync(ObjectKind.DOMAIN)
async def resync_domains(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all domains from Vercel."""
    logger.info("Starting domains resync")
    client = create_vercel_client()
    exporter = DomainExporter(client)
    async for domains_batch in exporter.get_paginated_resources():
        yield domains_batch


# Register webhook processors
ocean.add_webhook_processor("/webhook", DeploymentWebhookProcessor)
ocean.add_webhook_processor("/webhook", ProjectWebhookProcessor)
ocean.add_webhook_processor("/webhook", DomainWebhookProcessor)
