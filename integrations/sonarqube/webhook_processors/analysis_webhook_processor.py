from typing import cast
from loguru import logger
from initialize_client import init_sonar_client
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from webhook_processors.base_webhook_processor import BaseSonarQubeWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from integration import ObjectKind, SonarQubeOnPremAnalysisResourceConfig


class AnalysisWebhookProcessor(BaseSonarQubeWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [
            ObjectKind.ANALYSIS,
            ObjectKind.SASS_ANALYSIS,
            ObjectKind.ONPREM_ANALYSIS,
        ]

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        sonar_client = init_sonar_client()

        analysis_data = []

        project = await sonar_client.get_single_component(payload["project"])

        if ocean.integration_config["sonar_is_on_premise"]:
            logger.info(
                f"Processing SonarQube analysis webhook for project: {project['key']}"
            )
            if resource.kind == ObjectKind.ONPREM_ANALYSIS:
                resource_config = cast(SonarQubeOnPremAnalysisResourceConfig, resource)
                sonar_client.metrics = resource_config.selector.metrics
            analysis_data = await sonar_client.get_measures_for_all_pull_requests(
                project["key"]
            )
        else:
            logger.info(
                f"Processing SonarCloud analysis webhook for project: {project['key']}"
            )
            async for updated_analysis in sonar_client.get_analysis_by_project(project):
                analysis_data.extend(updated_analysis)

        return WebhookEventRawResults(
            updated_raw_results=analysis_data,
            deleted_raw_results=[],
        )
