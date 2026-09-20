from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)

from actions.exceptions import MissingExecutionPropertyError, TriggerIncidentError
from actions.trigger_incident_executor import (
    TriggerIncidentExecutor,
    TriggerIncidentInput,
)

INCIDENT_RESPONSE = {
    "id": "Q1QGYB805SG874",
    "html_url": "https://example.pagerduty.com/incidents/Q1QGYB805SG874",
    "title": "The server is on fire",
}


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-1",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="trigger_incident"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationActionType="trigger_incident",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> TriggerIncidentExecutor:
    with patch.object(TriggerIncidentExecutor, "__init__", lambda self: None):
        ex = TriggerIncidentExecutor()
        ex.client = MagicMock()
        ex.client.create_incident = AsyncMock(return_value=INCIDENT_RESPONSE)
        return ex


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.post_run_log = AsyncMock()
    client.report_run_completed = AsyncMock()
    return client


@pytest.mark.asyncio
class TestTriggerIncidentExecutor:
    async def test_happy_path(
        self, executor: TriggerIncidentExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run(
            {
                "service": "P00BUSE",
                "title": "The server is on fire",
                "fromEmail": "oncall@example.com",
                "details": "Disk is full",
                "urgency": "high",
            }
        )
        with patch("actions.trigger_incident_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        executor.client.create_incident.assert_awaited_once_with(  # type: ignore[attr-defined]
            service_id="P00BUSE",
            title="The server is on fire",
            from_email="oncall@example.com",
            details="Disk is full",
            urgency="high",
            incident_key=None,
            escalation_policy_id=None,
        )
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message=f"Incident created: {INCIDENT_RESPONSE['html_url']}",
        )

    async def test_missing_service_raises(
        self, executor: TriggerIncidentExecutor
    ) -> None:
        run = make_run({"title": "Test", "fromEmail": "oncall@example.com"})
        with pytest.raises(MissingExecutionPropertyError, match="Field required"):
            await executor.execute(run)

    async def test_missing_title_raises(
        self, executor: TriggerIncidentExecutor
    ) -> None:
        run = make_run({"service": "P00BUSE", "fromEmail": "oncall@example.com"})
        with pytest.raises(MissingExecutionPropertyError, match="Field required"):
            await executor.execute(run)

    async def test_missing_from_email_raises(
        self, executor: TriggerIncidentExecutor
    ) -> None:
        run = make_run({"service": "P00BUSE", "title": "Test"})
        with pytest.raises(MissingExecutionPropertyError, match="Field required"):
            await executor.execute(run)

    async def test_invalid_urgency_raises(
        self, executor: TriggerIncidentExecutor
    ) -> None:
        run = make_run(
            {
                "service": "P00BUSE",
                "title": "Test",
                "fromEmail": "oncall@example.com",
                "urgency": "critical",
            }
        )
        with pytest.raises(
            MissingExecutionPropertyError,
            match=r"Input should be 'high' or 'low'",
        ):
            await executor.execute(run)

    async def test_api_error_raises_trigger_error(
        self, executor: TriggerIncidentExecutor, mock_port_client: MagicMock
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "Invalid From header"}
        executor.client.create_incident = AsyncMock(  # type: ignore[method-assign]
            side_effect=httpx.HTTPStatusError(
                "400",
                request=MagicMock(),
                response=mock_response,
            ),
        )
        run = make_run(
            {
                "service": "P00BUSE",
                "title": "Test",
                "fromEmail": "oncall@example.com",
            }
        )
        with (
            patch("actions.trigger_incident_executor.ocean") as mock_ocean,
            pytest.raises(TriggerIncidentError, match="Invalid From header"),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)


class TestTriggerIncidentInput:
    def test_from_execution_properties_happy_path(self) -> None:
        inputs = TriggerIncidentInput.from_execution_properties(
            {
                "service": "P00BUSE",
                "title": "The server is on fire",
                "fromEmail": "oncall@example.com",
                "details": "Disk is full",
                "urgency": "high",
                "incidentKey": "dedup-key",
                "escalationPolicyId": "P7LVMYP",
            }
        )

        assert inputs.service == "P00BUSE"
        assert inputs.to_client_kwargs() == {
            "service_id": "P00BUSE",
            "title": "The server is on fire",
            "from_email": "oncall@example.com",
            "details": "Disk is full",
            "urgency": "high",
            "incident_key": "dedup-key",
            "escalation_policy_id": "P7LVMYP",
        }

    def test_ignores_unknown_execution_properties(self) -> None:
        inputs = TriggerIncidentInput.from_execution_properties(
            {
                "service": "P00BUSE",
                "title": "Test",
                "fromEmail": "oncall@example.com",
                "unexpectedField": "ignored",
            }
        )

        assert inputs.service == "P00BUSE"

    def test_rejects_empty_required_string(self) -> None:
        with pytest.raises(MissingExecutionPropertyError, match="must not be empty"):
            TriggerIncidentInput.from_execution_properties(
                {
                    "service": "P00BUSE",
                    "title": "   ",
                    "fromEmail": "oncall@example.com",
                }
            )
