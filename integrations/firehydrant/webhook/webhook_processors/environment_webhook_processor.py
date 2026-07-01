from typing import Any

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from init_client import init_client
from utils import ObjectKind
from webhook.webhook_processors.base_webhook_processor import (
    FirehydrantBaseWebhookProcessor,
)


class EnvironmentWebhookProcessor(FirehydrantBaseWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return "environments" in event.payload.get("data", {})

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ENVIRONMENT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = init_client()
        updated: list[dict[str, Any]] = []
        for environment in payload["data"]["environments"]:
            env_data = await client.get_single_environment(
                environment_id=environment["id"]
            )
            updated.append(env_data)
        return WebhookEventRawResults(
            updated_raw_results=updated,
            deleted_raw_results=[],
        )
