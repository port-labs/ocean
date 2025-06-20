from initialize_client import init_sonar_client
from webhook_processors.base_webhook_processor import BaseSonarQubeWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from typing import cast
from loguru import logger

from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from integration import (
    ObjectKind,
    SonarQubeIssueResourceConfig,
)


class IssueWebhookProcessor(BaseSonarQubeWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUES]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:

        sonar_client = init_sonar_client()

        selector = cast(SonarQubeIssueResourceConfig, resource_config).selector
        query_params = selector.generate_request_params()

        project = await sonar_client.get_single_component(payload["project"])

        updated_issue_results = []

        async for updated_issue in sonar_client.get_issues_by_component(
            project, query_params
        ):

            if updated_issue:
                updated_issue_results.extend(updated_issue)

        if not updated_issue_results:
            logger.warning("Could not fetch updated issue data. Using webhook payload")
            updated_issue_results.append(payload)

        return WebhookEventRawResults(
            updated_raw_results=updated_issue_results,
            deleted_raw_results=[],
        )
