import typing

from loguru import logger
from port_ocean.context.event import event as ocean_event
from pydantic.v1 import ValidationError

from newrelic_integration.core.issues import IssueEvent
from newrelic_integration.overrides import NewRelicPortAppConfig
from newrelic_integration.webhook.issue_event_utils import (
    enrich_issue_entity_relations,
    get_issue_kinds,
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


class IssueWebhookProcessor(BaseWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return await self.validate_payload(event.payload)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        app_config = typing.cast(NewRelicPortAppConfig, ocean_event.port_app_config)
        return get_issue_kinds(app_config)

    async def validate_payload(self, payload: EventPayload) -> bool:
        try:
            IssueEvent(**payload)
            return True
        except ValidationError:
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        issue_record = dict(payload)
        issue_id = issue_record.get("issueId")
        issue_state = issue_record.get("state")

        with logger.contextualize(issue_id=issue_id, issue_state=issue_state):
            logger.info("Processing issue event")

            await enrich_issue_entity_relations(issue_record)

            return WebhookEventRawResults(
                updated_raw_results=[issue_record],
                deleted_raw_results=[],
            )
