from initialize_client import init_sonar_client
from utils import extract_metrics_from_payload
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from webhook_processors.base_webhook_processor import BaseSonarQubeWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from integration import ObjectKind


class ProjectWebhookProcessor(BaseSonarQubeWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PROJECTS, ObjectKind.PROJECTS_GA]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        metrics = extract_metrics_from_payload(payload)
        sonar_client = init_sonar_client(metrics)

        project = await sonar_client.get_single_component(payload["project"])
        project_data = await sonar_client.get_single_project(project)

        return WebhookEventRawResults(
            updated_raw_results=[project_data],
            deleted_raw_results=[],
        )
