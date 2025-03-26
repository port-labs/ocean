from initialize_client import init_sonar_client
from utils import extract_metrics_from_payload
from webhook_processors.base_webhook_processor import BaseSonarQubeWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from integration import ObjectKind


class IssueWebhookProcessor(BaseSonarQubeWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUES]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        metrics = extract_metrics_from_payload(payload)
        sonar_client = init_sonar_client(metrics)

        project = await sonar_client.get_single_component(payload["project"])
        issues = []

        async for issues_batch in sonar_client.get_issues_by_component(project):
            issues.extend(issues_batch)

        return WebhookEventRawResults(
            updated_raw_results=issues,
            deleted_raw_results=[],
        )
