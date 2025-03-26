from initialize_client import init_sonar_client
from utils import extract_metrics_from_payload
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from webhook_processors.base_webhook_processor import BaseSonarQubeWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from integration import ObjectKind


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
        metrics = [
            condition["metric"]
            for condition in payload.get("qualityGate", {}).get("conditions", [])
        ]
        sonar_client = init_sonar_client(metrics)

        analysis_data = []

        if ocean.integration_config["sonar_is_on_premise"]:
            metrics = extract_metrics_from_payload(payload)
            project = await sonar_client.get_single_component(payload["project"])
            analysis_data = await sonar_client.get_measures_for_all_pull_requests(
                project["key"]
            )
        else:
            analysis_data = [await sonar_client.get_analysis_for_task(payload)]

        return WebhookEventRawResults(
            updated_raw_results=analysis_data,
            deleted_raw_results=[],
        )
