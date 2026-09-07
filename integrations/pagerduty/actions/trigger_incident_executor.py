from __future__ import annotations

from typing import Any, Literal

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from pydantic import field_validator

from actions.abstract_action_input import AbstractPagerDutyActionInput
from actions.abstract_pagerduty_executor import AbstractPagerDutyExecutor
from actions.exceptions import TriggerIncidentError


class TriggerIncidentInput(AbstractPagerDutyActionInput):
    service: str
    title: str
    fromEmail: str
    details: str | None = None
    urgency: Literal["high", "low"] | None = None
    priorityId: str | None = None
    incidentKey: str | None = None
    escalationPolicyId: str | None = None

    @field_validator("service", "title", "fromEmail")
    @classmethod
    def non_empty(cls, value: str) -> str:
        return cls.non_empty_str(value)

    def to_client_kwargs(self) -> dict[str, Any]:
        return {
            "service_id": self.service,
            "title": self.title,
            "from_email": self.fromEmail,
            "details": self.details,
            "urgency": self.urgency,
            "priority_id": self.priorityId,
            "incident_key": self.incidentKey,
            "escalation_policy_id": self.escalationPolicyId,
        }


class TriggerIncidentExecutor(AbstractPagerDutyExecutor):
    ACTION_NAME = "trigger_incident"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        inputs = TriggerIncidentInput.from_execution_properties(
            run.execution_properties
        )

        await ocean.port_client.post_run_log(
            run,
            f"Creating PagerDuty incident on service {inputs.service}",
            should_raise=False,
        )

        try:
            incident = await self.client.create_incident(**inputs.to_client_kwargs())
        except httpx.HTTPStatusError as e:
            raise TriggerIncidentError.from_response(
                e.response,
                f"Could not create incident on service '{inputs.service}'",
            )

        if not incident or not all(k in incident for k in ("id", "html_url")):
            raise TriggerIncidentError(
                "Failed to create incident: PagerDuty returned an empty or incomplete response"
            )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Incident created: {incident['html_url']}",
        )
        logger.info(
            f"Incident {incident['id']} created on service {inputs.service}",
            incident_id=incident["id"],
            service_id=inputs.service,
        )
