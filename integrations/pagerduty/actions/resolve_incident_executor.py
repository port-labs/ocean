from __future__ import annotations

from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from pydantic import field_validator

from actions.abstract_action_input import AbstractPagerDutyActionInput
from actions.abstract_pagerduty_executor import AbstractPagerDutyExecutor
from actions.exceptions import UpdateIncidentError


class ResolveIncidentInput(AbstractPagerDutyActionInput):
    incidentId: str
    fromEmail: str
    resolution: str | None = None

    @field_validator("incidentId", "fromEmail")
    @classmethod
    def non_empty(cls, value: str) -> str:
        return cls.non_empty_str(value)

    @field_validator("resolution", mode="before")
    @classmethod
    def normalize_resolution(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        return str(value).strip()

    def to_client_kwargs(self) -> dict[str, Any]:
        return {
            "incident_id": self.incidentId,
            "from_email": self.fromEmail,
            "status": "resolved",
        }


class ResolveIncidentExecutor(AbstractPagerDutyExecutor):
    ACTION_NAME = "resolve_incident"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        incident_id = run.execution_properties.get("incidentId")
        if not incident_id:
            return None
        return str(incident_id)

    async def execute(self, run: IntegrationRun) -> None:
        inputs = ResolveIncidentInput.from_execution_properties(
            run.execution_properties
        )

        log_message = f"Resolving PagerDuty incident {inputs.incidentId}"
        if inputs.resolution:
            log_message = f"{log_message} with resolution note"
        await ocean.port_client.post_run_log(
            run,
            log_message,
            should_raise=False,
        )

        try:
            incident = await self.client.update_incident(**inputs.to_client_kwargs())
        except httpx.HTTPStatusError as e:
            raise UpdateIncidentError.from_response(
                e.response,
                f"Could not resolve incident '{inputs.incidentId}'",
            )

        note_added = False
        if inputs.resolution:
            try:
                await self.client.create_incident_note(
                    incident_id=inputs.incidentId,
                    from_email=inputs.fromEmail,
                    content=inputs.resolution,
                )
                note_added = True
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"Incident {inputs.incidentId} resolved but failed to add resolution note",
                    incident_id=inputs.incidentId,
                    response=e.response.text,
                )

        completion_message = f"Incident resolved: {incident['html_url']}"
        if note_added:
            completion_message = (
                f"{completion_message}. Resolution note: {inputs.resolution}"
            )
        elif inputs.resolution:
            completion_message = (
                f"{completion_message}. Resolution note could not be added"
            )
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=completion_message,
        )
        logger.info(
            f"Incident {inputs.incidentId} resolved",
            incident_id=inputs.incidentId,
        )
