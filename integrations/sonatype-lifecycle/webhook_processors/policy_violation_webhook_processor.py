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


class PolicyViolationWebhookProcessor(SonatypeAbstractWebhookProcessor):
    """Refresh the policy-violation entities for a re-evaluated report.

    Note: a live evaluation event tells us the *current* violations for the
    report but not which historical ones were fixed. Violations that have been
    resolved since the last full sync are pruned on the next scheduled resync
    rather than immediately on the webhook.
    """

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            self._event_id(event) == APPLICATION_EVALUATION_EVENT
            and "applicationEvaluation" in event.payload
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.POLICY_VIOLATION]

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

        scan_data = await client.get_scan_data_for_single_report(
            application, stage, report_id
        )
        logger.info(
            f"Refreshing {len(scan_data['violations'])} policy violations for "
            f"{application.get('publicId')} at stage '{stage}'"
        )
        return WebhookEventRawResults(
            updated_raw_results=scan_data["violations"],
            deleted_raw_results=[],
        )
