from webhook_processors.base_webhook_processor import BaseSonarQubeWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.context.ocean import ocean

from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from client import SonarQubeClient
from integration import ObjectKind


class IssueWebhookProcessor(BaseSonarQubeWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUES]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        sonar_client = SonarQubeClient(
            ocean.integration_config.get("sonar_url", "https://sonarcloud.io"),
            ocean.integration_config["sonar_api_token"],
            ocean.integration_config.get("sonar_organization_id"),
            ocean.integration_config.get("app_host"),
            ocean.integration_config["sonar_is_on_premise"],
        )

        project = await sonar_client.get_single_component(payload.get("project", {}))
        issues = []

        async for issues_batch in sonar_client.get_issues_by_component(project):
            issues.extend(issues_batch)

        return WebhookEventRawResults(
            updated_raw_results=issues,
            deleted_raw_results=[],
        )
