from initialize_client import init_sonar_client
from utils import extract_metrics_from_payload
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
    SonarQubeIssueResourceConfig,
    SonarQubeProjectResourceConfig,
    SonarQubeOnPremAnalysisResourceConfig,
)


class ProjectWebhookProcessor(BaseSonarQubeWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PROJECTS, ObjectKind.PROJECTS_GA]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:

        logger.warning("Project webhook initiated")
        """
          metrics = extract_metrics_from_payload(payload)
        sonar_client = init_sonar_client(metrics)

        project = await sonar_client.get_single_component(payload["project"])
        project_data = await sonar_client.get_single_project(project)

        return WebhookEventRawResults(
            updated_raw_results=[project_data],
            deleted_raw_results=[],
        )


        """

        sonar_client = init_sonar_client()

        selector = cast(SonarQubeGAProjectResourceConfig, resource_config).selector
        sonar_client.metrics = selector.metrics

        project = await sonar_client.get_single_component(payload["project"])

        logger.warning(f'{project}')

        updated_project_results = []

        updated_project = await sonar_client.get_single_project(project)

        #print("updated_project", updated_project);
        logger.warning(f'{updated_project}')

        if updated_project:
            updated_project_results.append(updated_project)

        if not updated_project_results:
            logger.info(
                "Could not fetch updated project data. Using Webhook data"
            )
            updated_project_results.append(payload)

        logger.warning("Project webhook finished")

        return WebhookEventRawResults(
            updated_raw_results=updated_project_results,
            deleted_raw_results=[],
        )


