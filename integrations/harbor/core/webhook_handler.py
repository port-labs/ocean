from typing import Any

from fastapi import Request
from loguru import logger

from port_ocean.context.ocean import ocean

from ..utils.types import HarborWebhookEventType, HarborResourceType
from .client import HarborClient


def _extract_event_data(payload: dict[str, Any]) -> tuple[str, str, str | None]:
    """Extract project name, repo name, and digest from a webhook payload."""
    event_data = payload["event_data"]
    project_name = event_data["repository"]["namespace"]
    repo_name = event_data["repository"]["name"]
    digest = event_data["resources"][0].get("digest") if event_data.get("resources") else None
    return project_name, repo_name, digest


async def validate_webhook_secret(request: Request) -> bool:
    expected_secret = ocean.integration_config.get("harbor_webhook_secret")
    if not expected_secret:
        return True
    request_secret = request.headers.get("Authorization", "")
    return request_secret == expected_secret


async def process_webhook_event(
    payload: dict[str, Any], client: HarborClient
) -> None:
    event_type = payload.get("type", "")
    logger.info(f"Processing webhook event: {event_type}")

    project_name, repo_name, digest = _extract_event_data(payload)

    match event_type:
        case HarborWebhookEventType.PUSH_ARTIFACT | HarborWebhookEventType.SCAN_COMPLETED:
            if digest:
                artifact = await client.get_single_artifact(
                    project_name, repo_name, digest
                )
                await ocean.register_raw(HarborResourceType.ARTIFACT, [artifact])
                logger.info(
                    f"Upserted artifact '{digest}' "
                    f"from '{project_name}/{repo_name}'"
                )

        case HarborWebhookEventType.DELETE_ARTIFACT:
            if digest:
                await ocean.unregister_raw(
                    HarborResourceType.ARTIFACT,
                    [
                        {
                            "repository_name": f"{project_name}/{repo_name}",
                            "digest": digest,
                        }
                    ],
                )
                logger.info(
                    f"Deleted artifact '{digest}' "
                    f"from '{project_name}/{repo_name}'"
                )

        case HarborWebhookEventType.PULL_ARTIFACT:
            logger.debug(f"Ignoring pull event for '{project_name}/{repo_name}'")

        case _:
            logger.warning(f"Unhandled webhook event type: {event_type}")
