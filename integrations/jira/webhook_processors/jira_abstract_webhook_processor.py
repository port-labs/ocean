from typing import Any

from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventHeaders, EventPayload
from port_ocean.core.handlers.webhook.webhook_log_context import pick_nested_fields

_JIRA_LIVE_EVENT_PAYLOAD_PATHS = (
    "webhookEvent",
    "issue.key",
    "issue.id",
    "sprint.id",
    "board.id",
    "project.id",
)


class JiraAbstractWebhookProcessor(AbstractWebhookProcessor):
    def get_live_event_log_identifiers(
        self, payload: EventPayload, headers: EventHeaders
    ) -> dict[str, Any] | None:
        identifiers = pick_nested_fields(payload, _JIRA_LIVE_EVENT_PAYLOAD_PATHS)
        return identifiers or None
