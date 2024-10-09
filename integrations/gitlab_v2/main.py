from enum import StrEnum
from typing import Any
from loguru import logger

from gitlab_integration import GitLabIntegration
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class InvalidTokenException(Exception):
    ...


class ResourceKind(StrEnum):
    GROUP = "group"
    PROJECT = "project"
    MERGE_REQUEST = "merge_request"
    ISSUE = "issue"

RESOURCE_ENDPOINT_MAPPING = {
    ResourceKind.GROUP: "groups",
    ResourceKind.PROJECT: "projects",
    ResourceKind.MERGE_REQUEST: "merge_requests",
    ResourceKind.ISSUE: "issues"
}


gitlab_integration = GitLabIntegration()

@ocean.on_start()
async def on_start() -> None:
    logger.info(f"Starting musah_gitlab integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    await setup_application()



async def setup_application() -> None:
    app_host = ocean.integration_config["app_host"]
    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Gitlab"
        )
        return

    await gitlab_integration.initialize()



@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    webhook_event = data.get("event_type", "")
    object_attributes_action = data.get("object_attributes", {}).get("action", "")
    logger.info(
        f"Received webhook event: {webhook_event} with action: {object_attributes_action}"
    )

    await gitlab_integration.handle_webhook_event(webhook_event, object_attributes_action, data)

    return {"status": "success"}


@ocean.on_resync()
async def resync_resources(kind: ResourceKind) -> ASYNC_GENERATOR_RESYNC_TYPE:
    await gitlab_integration.initialize()
    resource = RESOURCE_ENDPOINT_MAPPING.get(kind)
    kind_configs = ocean.integration_config.get("gitlab_resources_config", {}).get(resource, {})
    if not kind_configs:
        logger.info(f"Resync initiated for '{kind}', but no additional enrichment configurations were found. Proceeding with the default resync process.")

    async for resource_kind in gitlab_integration.resync_resources(kind, kind_configs):
        yield resource_kind
