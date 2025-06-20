from initialize_client import init_sonar_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from webhook_processors.base_webhook_processor import BaseSonarQubeWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from typing import cast


from loguru import logger

from integration import (
    ObjectKind,
    SonarQubeGAProjectResourceConfig,
)


class ProjectWebhookProcessor(BaseSonarQubeWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PROJECTS, ObjectKind.PROJECTS_GA]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:

        sonar_client = init_sonar_client()

        selector = cast(SonarQubeGAProjectResourceConfig, resource_config).selector
        sonar_client.metrics = selector.metrics

        project = await sonar_client.get_single_component(payload["project"])

        updated_project_results = []

        updated_project = await sonar_client.get_single_project(project)

        if updated_project:
            updated_project_results.append(updated_project)

        if not updated_project_results:
            logger.info("Could not fetch updated project data. Using Webhook data")
            updated_project_results.append(payload)

        return WebhookEventRawResults(
            updated_raw_results=updated_project_results,
            deleted_raw_results=[],
        )
