from initialize_client import init_sonar_client
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from webhook_processors.base_webhook_processor import BaseSonarQubeWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from integration import ObjectKind
from typing import cast


from integration import (
    SonarQubeOnPremAnalysisResourceConfig,
)


class AnalysisWebhookProcessor(BaseSonarQubeWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [
            ObjectKind.ANALYSIS,
            ObjectKind.SASS_ANALYSIS,
            ObjectKind.ONPREM_ANALYSIS,
        ]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:

        sonar_client = init_sonar_client()

        analysis_data = []

        project = await sonar_client.get_single_component(payload["project"])

        if ocean.integration_config["sonar_is_on_premise"]:
            selector = cast(
                SonarQubeOnPremAnalysisResourceConfig, resource_config
            ).selector
            sonar_client.metrics = selector.metrics

            analysis_data = await sonar_client.get_measures_for_all_pull_requests(
                project["key"]
            )
        else:

            async for updated_analysis in sonar_client.get_analysis_by_project(project):
                if updated_analysis:
                    analysis_data.extend(updated_analysis)
            if not analysis_data:
                analysis_data.append(payload)

        return WebhookEventRawResults(
            updated_raw_results=analysis_data,
            deleted_raw_results=[],
        )
