from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class WebhookPingProcessor(_GithubAbstractWebhookProcessor):
    """
    Lightweight processor for GitHub `ping` webhooks.

    GitHub sends `ping` events when a webhook is created or updated so that
    consumers can verify connectivity and signature handling without
    mutating any resources in Port. We short-circuit here and only log
    the event so it shows up in observability, while returning empty
    results to the pipeline.
    """

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "ping"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        logger.error(
            "Handling GitHub ping webhook which does not map to any resource kinds; returning empty list"
        )
        return []

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
