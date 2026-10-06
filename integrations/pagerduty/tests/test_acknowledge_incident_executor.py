from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)

from actions.acknowledge_incident_executor import (
    AcknowledgeIncidentExecutor,
    AcknowledgeIncidentInput,
)
from actions.exceptions import MissingExecutionPropertyError, UpdateIncidentError

INCIDENT_RESPONSE = {
    "id": "Q1QGYB805SG874",
    "html_url": "https://example.pagerduty.com/incidents/Q1QGYB805SG874",
    "status": "acknowledged",
}


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-1",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="acknowledge_incident"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationActionType="acknowledge_incident",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> AcknowledgeIncidentExecutor:
    with patch.object(AcknowledgeIncidentExecutor, "__init__", lambda self: None):
        ex = AcknowledgeIncidentExecutor()
        ex.client = MagicMock()
        ex.client.update_incident = AsyncMock(return_value=INCIDENT_RESPONSE)
        return ex


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.post_run_log = AsyncMock()
    client.report_run_completed = AsyncMock()
    return client


@pytest.mark.asyncio
class TestAcknowledgeIncidentExecutor:
    async def test_happy_path(
        self, executor: AcknowledgeIncidentExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run(
            {
                "incidentId": "Q1QGYB805SG874",
                "fromEmail": "oncall@example.com",
            }
        )
        with patch("actions.acknowledge_incident_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        executor.client.update_incident.assert_awaited_once_with(  # type: ignore[attr-defined]
            incident_id="Q1QGYB805SG874",
            from_email="oncall@example.com",
            status="acknowledged",
        )
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message=f"Incident acknowledged: {INCIDENT_RESPONSE['html_url']}",
        )

    async def test_missing_incident_id_raises(
        self, executor: AcknowledgeIncidentExecutor
    ) -> None:
        run = make_run({"fromEmail": "oncall@example.com"})
        with pytest.raises(MissingExecutionPropertyError, match="Field required"):
            await executor.execute(run)

    async def test_missing_from_email_raises(
        self, executor: AcknowledgeIncidentExecutor
    ) -> None:
        run = make_run({"incidentId": "Q1QGYB805SG874"})
        with pytest.raises(MissingExecutionPropertyError, match="Field required"):
            await executor.execute(run)

    async def test_api_error_raises_update_error(
        self, executor: AcknowledgeIncidentExecutor, mock_port_client: MagicMock
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "Incident not found"}
        executor.client.update_incident = AsyncMock(  # type: ignore[method-assign]
            side_effect=httpx.HTTPStatusError(
                "404",
                request=MagicMock(),
                response=mock_response,
            ),
        )
        run = make_run(
            {
                "incidentId": "Q1QGYB805SG874",
                "fromEmail": "oncall@example.com",
            }
        )
        with (
            patch("actions.acknowledge_incident_executor.ocean") as mock_ocean,
            pytest.raises(UpdateIncidentError, match="Incident not found"),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

    async def test_partition_key_returns_incident_id(
        self, executor: AcknowledgeIncidentExecutor
    ) -> None:
        run = make_run(
            {
                "incidentId": "Q1QGYB805SG874",
                "fromEmail": "oncall@example.com",
            }
        )
        assert await executor._get_partition_key(run) == "Q1QGYB805SG874"

    async def test_partition_key_returns_none_when_incident_id_missing(
        self, executor: AcknowledgeIncidentExecutor
    ) -> None:
        run = make_run({"fromEmail": "oncall@example.com"})
        assert await executor._get_partition_key(run) is None


class TestAcknowledgeIncidentInput:
    def test_from_execution_properties_happy_path(self) -> None:
        inputs = AcknowledgeIncidentInput.from_execution_properties(
            {
                "incidentId": "Q1QGYB805SG874",
                "fromEmail": "oncall@example.com",
            }
        )

        assert inputs.to_client_kwargs() == {
            "incident_id": "Q1QGYB805SG874",
            "from_email": "oncall@example.com",
            "status": "acknowledged",
        }
