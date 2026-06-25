import typing

import httpx
from loguru import logger
from port_ocean.context.event import event as ocean_event
from pydantic.v1 import ValidationError

from newrelic_integration.core.issues import IssueEvent
from newrelic_integration.overrides import NewRelicPortAppConfig
from newrelic_integration.utils import NewRelicAnyResourceConfig
from newrelic_integration.webhook.issue_event_utils import (
    fetch_entities_for_resource,
    get_entity_kinds,
)
from newrelic_integration.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class EntityWebhookProcessor(BaseWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return await self.validate_payload(event.payload)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        app_config = typing.cast(NewRelicPortAppConfig, ocean_event.port_app_config)
        return get_entity_kinds(app_config)

    async def validate_payload(self, payload: EventPayload) -> bool:
        try:
            IssueEvent(**payload)
            return True
        except ValidationError:
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        entity_guids = payload.get("entityGuids", [])
        issue_id = payload.get("issueId")

        with logger.contextualize(issue_id=issue_id):
            logger.info(
                "Processing entity updates for issue event",
                resource_kind=resource_config.kind,
            )

            async with httpx.AsyncClient() as http_client:
                entities = await fetch_entities_for_resource(
                    http_client,
                    typing.cast(NewRelicAnyResourceConfig, resource_config),
                    entity_guids,
                )

            return WebhookEventRawResults(
                updated_raw_results=entities,
                deleted_raw_results=[],
            )
