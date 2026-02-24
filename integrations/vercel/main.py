"""
Ocean integration entry-point.

Contains:
  - Resync handlers for all resource kinds (teams, projects, deployments, domains)
  - A webhook endpoint that processes real-time Vercel events
  - Startup hook that logs the configured scope
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request, Response
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import VercelClient, create_client

logger = logging.getLogger(__name__)

# ── Startup ────────────────────────────────────────────────────────────────────


@ocean.on_start()
async def on_start() -> None:
    cfg = ocean.integration_config
    team_id = cfg.get("teamId") or "personal account"
    logger.info("Vercel integration starting — scope: %s", team_id)
    if not cfg.get("webhookSecret"):
        logger.warning(
            "webhookSecret is not configured. Incoming webhook payloads will NOT "
            "be signature-validated. Set webhookSecret to harden your deployment."
        )


# ── Resync handlers ────────────────────────────────────────────────────────────


@ocean.on_resync("team")
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async with create_client() as client:
        async for page in client.get_teams():
            logger.info("Syncing %d team(s)", len(page))
            yield page


@ocean.on_resync("project")
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async with create_client() as client:
        async for page in client.get_projects():
            logger.info("Syncing %d project(s)", len(page))
            yield page


@ocean.on_resync("deployment")
async def resync_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Pull deployments for every project.

    We iterate projects first so we can attach a projectId to each deployment
    page, making relation resolution reliable even when Vercel omits the field.
    """
    async with create_client() as client:
        async for project in client.get_all_projects_flat():
            project_id = project["id"]
            project_name = project.get("name", project_id)
            async for page in client.get_deployments(project_id=project_id):
                # Ensure each deployment knows which project it belongs to.
                for deployment in page:
                    deployment.setdefault("name", project_name)
                    # Inject projectId so the Port relation can be resolved
                    # reliably — the Vercel API does not always include it.
                    deployment["projectId"] = project_id
                logger.info(
                    "Syncing %d deployment(s) for project %s",
                    len(page),
                    project_name,
                )
                yield page


@ocean.on_resync("domain")
async def resync_domains(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Pull domains for every project."""
    async with create_client() as client:
        async for project in client.get_all_projects_flat():
            project_id = project["id"]
            async for page in client.get_project_domains(project_id):
                logger.info(
                    "Syncing %d domain(s) for project %s",
                    len(page),
                    project_id,
                )
                yield page


# ── Webhook endpoint ───────────────────────────────────────────────────────────

# Map Vercel webhook event types to the Ocean resource kinds they affect.
_EVENT_KIND_MAP: dict[str, str] = {
    "deployment.created": "deployment",
    "deployment.succeeded": "deployment",
    "deployment.ready": "deployment",
    "deployment.error": "deployment",
    "deployment.canceled": "deployment",
    "deployment.promoted": "deployment",
    "deployment.deleted": "deployment",
    "project.created": "project",
    "project.removed": "project",
    "domain.created": "domain",
    "domain.deleted": "domain",
}

_DELETION_EVENTS: frozenset[str] = frozenset(
    {"deployment.deleted", "project.removed", "domain.deleted"}
)


@ocean.router.post("/webhook")
async def handle_vercel_webhook(request: Request) -> Response:
    """
    Receive real-time events from Vercel and upsert / delete the affected
    Port entities immediately — without waiting for the next scheduled resync.

    Configure the webhook in the Vercel dashboard:
      https://vercel.com/account/webhooks  (personal)
      https://vercel.com/teams/<slug>/settings/webhooks  (team)
    """
    body = await request.body()

    # ── Signature validation ──────────────────────────────────────────────
    secret = ocean.integration_config.get("webhookSecret")
    if secret:
        sig_header = request.headers.get("x-vercel-signature", "")
        if not VercelClient.verify_webhook_signature(body, sig_header, secret):
            logger.warning("Webhook signature validation failed — rejecting request")
            return Response(content="Invalid signature", status_code=401)

    payload: dict[str, Any] = await request.json()
    event_type: str = payload.get("type", "")
    logger.info("Received Vercel webhook event: %s", event_type)

    kind = _EVENT_KIND_MAP.get(event_type)
    if kind is None:
        logger.debug("Unhandled Vercel event type: %s — ignoring", event_type)
        return Response(content="Event type not handled", status_code=200)

    # Vercel webhook payload shape:
    # { "type": "deployment.created", "payload": { "deployment": {...} } }
    event_payload = payload.get("payload", {})
    entity_data = _extract_entity(kind, event_payload)

    if event_type in _DELETION_EVENTS:
        await _handle_deletion(kind, entity_data)
    else:
        await _handle_upsert(kind, entity_data, event_payload)

    return Response(content="OK", status_code=200)


# ── Webhook helpers ────────────────────────────────────────────────────────────


def _extract_entity(kind: str, event_payload: dict[str, Any]) -> dict[str, Any]:
    """Pull the primary entity dict out of a Vercel webhook payload."""
    if kind == "deployment":
        return event_payload.get("deployment", event_payload)
    if kind == "project":
        return event_payload.get("project", event_payload)
    if kind == "domain":
        return event_payload.get("domain", event_payload)
    return event_payload


async def _handle_upsert(
    kind: str,
    entity_data: dict[str, Any],
    event_payload: dict[str, Any],
) -> None:
    """Register a single entity update with Port."""
    if kind == "deployment":
        # Attach the project name so the relation can be resolved.
        project_info = event_payload.get("project", {})
        entity_data.setdefault("name", project_info.get("name"))

    logger.info(
        "Upserting %s entity: %s", kind, entity_data.get("id") or entity_data.get("uid")
    )
    await ocean.register_raw(kind, [entity_data])


async def _handle_deletion(kind: str, entity_data: dict[str, Any]) -> None:
    """Unregister a deleted entity from Port."""
    # Derive the entity identifier the same way as the mapping does.
    if kind == "deployment":
        identifier = entity_data.get("uid") or entity_data.get("id")
    elif kind == "domain":
        identifier = entity_data.get("name")
    else:
        identifier = entity_data.get("id")

    if not identifier:
        logger.warning("Could not determine identifier for deleted %s — skipping", kind)
        return

    logger.info("Deleting %s entity: %s", kind, identifier)
    await ocean.unregister_raw(kind, [entity_data])
