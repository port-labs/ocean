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


class AcknowledgeIncidentInput(AbstractPagerDutyActionInput):
    incidentId: str
    fromEmail: str

    @field_validator("incidentId", "fromEmail")
    @classmethod
    def non_empty(cls, value: str) -> str:
        return cls.non_empty_str(value)

    def to_client_kwargs(self) -> dict[str, Any]:
        return {
            "incident_id": self.incidentId,
            "from_email": self.fromEmail,
            "status": "acknowledged",
        }


class AcknowledgeIncidentExecutor(AbstractPagerDutyExecutor):
    ACTION_NAME = "acknowledge_incident"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        incident_id = run.execution_properties.get("incidentId")
        if not incident_id:
            return None
        return str(incident_id)

    async def execute(self, run: IntegrationRun) -> None:
        inputs = AcknowledgeIncidentInput.from_execution_properties(
            run.execution_properties
        )

        await ocean.port_client.post_run_log(
            run,
            f"Acknowledging PagerDuty incident {inputs.incidentId}",
            should_raise=False,
        )

        try:
            incident = await self.client.update_incident(**inputs.to_client_kwargs())
        except httpx.HTTPStatusError as e:
            raise UpdateIncidentError.from_response(
                e.response,
                f"Could not acknowledge incident '{inputs.incidentId}'",
            )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Incident acknowledged: {incident['html_url']}",
        )
        logger.info(
            f"Incident {inputs.incidentId} acknowledged",
            incident_id=inputs.incidentId,
        )
