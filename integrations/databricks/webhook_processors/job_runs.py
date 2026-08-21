from typing import Optional

from loguru import logger
from clients.databricks import DatabricksClient
from consts import JOB_RUN_LIFECYCLE_EVENTS
from kinds import Kinds
from webhook_processors.abstract import DatabricksAbstractWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class JobRunWebhookProcessor(DatabricksAbstractWebhookProcessor):
    @staticmethod
    def _extract_run_id(payload: EventPayload) -> Optional[str]:
        run_id = (
            payload.get("run_id") or payload.get("runId") or payload.get("job_run_id")
        )
        if run_id is None:
            details = payload.get("event_details") or payload.get("eventDetails") or {}
            run_id = details.get("run_id") or details.get("runId")
        return str(run_id) if run_id is not None else None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        payload = event.payload
        event_type = payload.get("event_type") or payload.get("eventType")
        if event_type is not None and event_type not in JOB_RUN_LIFECYCLE_EVENTS:
            return False
        return bool(self._extract_run_id(payload))

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.JOB_RUNS]

    async def validate_payload(self, payload: EventPayload) -> bool:
        return bool(self._extract_run_id(payload))

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = DatabricksClient.from_ocean_configuration()
        run_id = self._extract_run_id(payload)
        logger.info(f"Handling Databricks job run webhook for run_id={run_id}")

        run = await client.get_job_run(run_id) if run_id else {}
        runs = [run] if run else []

        return WebhookEventRawResults(
            updated_raw_results=runs,
            deleted_raw_results=[],
        )
