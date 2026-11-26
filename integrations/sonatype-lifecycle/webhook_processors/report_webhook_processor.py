from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from initialize_client import get_sonatype_client
from kinds import ObjectKind
from webhook_processors._base import (
    APPLICATION_EVALUATION_EVENT,
    SonatypeAbstractWebhookProcessor,
)


class ReportWebhookProcessor(SonatypeAbstractWebhookProcessor):
    """Refresh a report entity when an application is (re)evaluated."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            self._event_id(event) == APPLICATION_EVALUATION_EVENT
            and "applicationEvaluation" in event.payload
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPORT]

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

        logger.info(
            f"Handling evaluation of application {application.get('publicId')} "
            f"at stage '{stage}' (report {report_id})"
        )
        scan_data = await client.get_scan_data_for_single_report(
            application, stage, report_id
        )
        return WebhookEventRawResults(
            updated_raw_results=scan_data["reports"],
            deleted_raw_results=[],
        )
