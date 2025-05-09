from loguru import logger
from newrelic_integration.webhook.processors.base_webhook_processor import (
    _NewRelicAbstractWebhookProcessor,
)
from newrelic_integration.core.issues import IssueEvent, IssuesHandler
from newrelic_integration.core.entities import EntitiesHandler
from port_ocean.utils import http_async_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class IssueWebhookProcessor(_NewRelicAbstractWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["newRelicAlert"]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        issues_handler = IssuesHandler(http_async_client)
        issue_event = IssueEvent(**payload)
        issue_record = issue_event.dict(by_alias=True)

        # Fetch entityGuids if not already present
        if "entityGuids" not in issue_record or not isinstance(
            issue_record["entityGuids"], list
        ):
            entity_guids = await issues_handler.get_issue_entity_guids(
                issue_record["id"]
            )
            if entity_guids:
                issue_record["entityGuids"] = entity_guids
            else:
                issue_record["entityGuids"] = []

        if "entityGuids" in issue_record and isinstance(
            issue_record["entityGuids"], list
        ):
            for entity_guid in issue_record["entityGuids"]:
                try:
                    entity = await EntitiesHandler(http_async_client).get_entity(
                        entity_guid
                    )
                    entity_type = entity["type"]
                    issue_record.setdefault(
                        f"__{entity_type}",
                        {},
                    ).setdefault(
                        "entity_guids", []
                    ).append(entity_guid)
                except Exception as e:
                    logger.error(f"Error fetching entity {entity_guid}: {e}")
                    continue

        return WebhookEventRawResults(
            updated_raw_results=[issue_record],
            deleted_raw_results=[],
        )
