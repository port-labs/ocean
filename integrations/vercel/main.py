from typing import Any

from fastapi import Request, Response
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from vercel.clients.client_factory import create_vercel_client
from vercel.clients.http.vercel_client import VercelClient
from vercel.core.exporters import (
    DeploymentExporter,
    DomainExporter,
    ProjectExporter,
    TeamExporter,
)
from vercel.helpers.utils import ObjectKind, extract_entity
from vercel.webhook.events import DELETION_EVENTS, EVENT_KIND_MAP


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
    async with create_vercel_client() as client:
        exporter = TeamExporter(client)
        async for teams_batch in exporter.get_paginated_resources():
            yield teams_batch


@ocean.on_resync(ObjectKind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all projects from Vercel."""
    logger.info("Starting projects resync")
    async with create_vercel_client() as client:
        exporter = ProjectExporter(client)
        async for projects_batch in exporter.get_paginated_resources():
            yield projects_batch


@ocean.on_resync(ObjectKind.DEPLOYMENT)
async def resync_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all deployments from Vercel."""
    logger.info("Starting deployments resync")
    async with create_vercel_client() as client:
        exporter = DeploymentExporter(client)
        async for deployments_batch in exporter.get_paginated_resources():
            yield deployments_batch


@ocean.on_resync(ObjectKind.DOMAIN)
async def resync_domains(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all domains from Vercel."""
    logger.info("Starting domains resync")
    async with create_vercel_client() as client:
        exporter = DomainExporter(client)
        async for domains_batch in exporter.get_paginated_resources():
            yield domains_batch


@ocean.router.post("/webhook")
async def handle_vercel_webhook(request: Request) -> Response:
    """
    Receive real-time events from Vercel and upsert/delete affected entities.

    Configure the webhook in your Vercel dashboard:
      https://vercel.com/account/webhooks (personal)
      https://vercel.com/teams/<slug>/settings/webhooks (team)
    """
    body = await request.body()

    # Validate webhook signature if secret is configured
    secret = ocean.integration_config.get("webhookSecret")
    if secret:
        sig_header = request.headers.get("x-vercel-signature", "")
        if not VercelClient.verify_webhook_signature(body, sig_header, secret):
            logger.warning("Webhook signature validation failed")
            return Response(content="Invalid signature", status_code=401)

    payload: dict[str, Any] = await request.json()
    event_type: str = payload.get("type", "")
    logger.info(f"Received Vercel webhook event: {event_type}")

    kind = EVENT_KIND_MAP.get(event_type)
    if kind is None:
        logger.debug(f"Unhandled event type: {event_type}")
        return Response(content="Event type not handled", status_code=200)

    event_payload = payload.get("payload", {})
    entity_data = extract_entity(kind, event_payload)

    if event_type in DELETION_EVENTS:
        await _handle_deletion(kind, entity_data)
    else:
        await _handle_upsert(kind, entity_data, event_payload)

    return Response(content="OK", status_code=200)


async def _handle_upsert(
    kind: str,
    entity_data: dict[str, Any],
    event_payload: dict[str, Any],
) -> None:
    """Register a single entity update with Port."""
    if kind == ObjectKind.DEPLOYMENT:
        project_info = event_payload.get("project", {})
        entity_data.setdefault("name", project_info.get("name"))

    identifier = (
        entity_data.get("uid") or entity_data.get("id") or entity_data.get("name")
    )
    logger.info(f"Upserting {kind} entity: {identifier}")
    await ocean.register_raw(kind, [entity_data])


async def _handle_deletion(kind: str, entity_data: dict[str, Any]) -> None:
    """Unregister a deleted entity from Port."""
    if kind == ObjectKind.DEPLOYMENT:
        identifier = entity_data.get("uid") or entity_data.get("id")
        deletion_payload = {"uid": identifier}
    elif kind == ObjectKind.DOMAIN:
        identifier = entity_data.get("name")
        deletion_payload = {"name": identifier}
    else:
        identifier = entity_data.get("id")
        deletion_payload = {"id": identifier}

    if not identifier:
        logger.warning(f"Could not determine identifier for deleted {kind}")
        return

    logger.info(f"Deleting {kind} entity: {identifier}")
    await ocean.unregister_raw(kind, [deletion_payload])
