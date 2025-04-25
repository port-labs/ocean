import base64
from typing import Any

from loguru import logger
from newrelic_integration.core.issues import IssueEvent, IssuesHandler
from newrelic_integration.core.entities import EntitiesHandler
import httpx
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class IssueWebhookProcessor(AbstractWebhookProcessor):

    async def should_process_event(self, event: WebhookEvent) -> bool:
        authorization = event.headers.get("authorization")
        webhook_secret = ocean.integration_config.get("webhook_secret")

        if authorization:
            try:
                auth_type, encoded_token = authorization.split(" ", 1)
                if auth_type.lower() != "basic":
                    return False

                decoded = base64.b64decode(encoded_token).decode("utf-8")
                _, token = decoded.split(":", 1)
                return token == webhook_secret
            except (ValueError, UnicodeDecodeError):
                return False
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["newRelicAlert"]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        async with httpx.AsyncClient() as http_client:
            issues_handler = IssuesHandler(http_client)
            try:
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
                            entity = await EntitiesHandler(http_client).get_entity(
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
            except Exception as e:
                logger.error(f"Error processing issue webhook event: {e}")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )

    async def authenticate(
        self, payload: EventPayload, headers: dict[str, Any]
    ) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True
