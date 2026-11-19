from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from initialize_client import get_sonatype_client
from kinds import ObjectKind
from utils import read_include_remediation
from webhook_processors._base import (
    APPLICATION_EVALUATION_EVENT,
    SonatypeAbstractWebhookProcessor,
)


class ComponentWebhookProcessor(SonatypeAbstractWebhookProcessor):
    """Refresh component entities (and their fix recommendations) on evaluation."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            self._event_id(event) == APPLICATION_EVALUATION_EVENT
            and "applicationEvaluation" in event.payload
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.COMPONENT]

    async def validate_payload(self, payload: EventPayload) -> bool:
        evaluation = payload.get("applicationEvaluation", {})
        required = {"application", "stage", "reportId"}
        return not (required - evaluation.keys()) and "id" in evaluation.get(
            "application", {}
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = get_sonatype_client()
        evaluation = payload["applicationEvaluation"]
        application = evaluation["application"]
        stage = evaluation["stage"]
        report_id = evaluation["reportId"]

        # Read by attribute (not isinstance): Ocean's runtime selector often
        # fails ComponentSelector checks and would skip remediation otherwise.
        include_remediation = read_include_remediation(resource_config.selector)

        data = await client.get_component_data_for_single_report(
            application, stage, report_id, include_remediation=include_remediation
        )
        logger.info(
            f"Refreshing {len(data['components'])} components for "
            f"{application.get('publicId')} at stage '{stage}'"
        )
        return WebhookEventRawResults(
            updated_raw_results=data["components"],
            deleted_raw_results=[],
        )
