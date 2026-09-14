from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)

from actions.exceptions import MissingExecutionPropertyError, UpdateIncidentError
from actions.resolve_incident_executor import (
    ResolveIncidentExecutor,
    ResolveIncidentInput,
)

INCIDENT_RESPONSE = {
    "id": "Q1QGYB805SG874",
    "html_url": "https://example.pagerduty.com/incidents/Q1QGYB805SG874",
    "status": "resolved",
}


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-1",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="resolve_incident"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationActionType="resolve_incident",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> ResolveIncidentExecutor:
    with patch.object(ResolveIncidentExecutor, "__init__", lambda self: None):
        ex = ResolveIncidentExecutor()
        ex.client = MagicMock()
        ex.client.update_incident = AsyncMock(return_value=INCIDENT_RESPONSE)
        ex.client.create_incident_note = AsyncMock()
        return ex


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.post_run_log = AsyncMock()
    client.report_run_completed = AsyncMock()
    return client


@pytest.mark.asyncio
class TestResolveIncidentExecutor:
    async def test_happy_path(
        self, executor: ResolveIncidentExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run(
            {
                "incidentId": "Q1QGYB805SG874",
                "fromEmail": "oncall@example.com",
                "resolution": "Restarted the service",
            }
        )
        with patch("actions.resolve_incident_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        executor.client.update_incident.assert_awaited_once_with(  # type: ignore[attr-defined]
            incident_id="Q1QGYB805SG874",
            from_email="oncall@example.com",
            status="resolved",
        )
        executor.client.create_incident_note.assert_awaited_once_with(  # type: ignore[attr-defined]
            incident_id="Q1QGYB805SG874",
            from_email="oncall@example.com",
            content="Restarted the service",
        )
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message=(
                f"Incident resolved: {INCIDENT_RESPONSE['html_url']}. "
                "Resolution note: Restarted the service"
            ),
        )

    async def test_happy_path_without_resolution(
        self, executor: ResolveIncidentExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run(
            {
                "incidentId": "Q1QGYB805SG874",
                "fromEmail": "oncall@example.com",
            }
        )
        with patch("actions.resolve_incident_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        executor.client.update_incident.assert_awaited_once_with(  # type: ignore[attr-defined]
            incident_id="Q1QGYB805SG874",
            from_email="oncall@example.com",
            status="resolved",
        )
        executor.client.create_incident_note.assert_not_called()  # type: ignore[attr-defined]

    async def test_note_failure_still_reports_success(
        self, executor: ResolveIncidentExecutor, mock_port_client: MagicMock
    ) -> None:
        mock_response = MagicMock()
        mock_response.text = "Forbidden"
        executor.client.create_incident_note = AsyncMock(  # type: ignore[method-assign]
            side_effect=httpx.HTTPStatusError(
                "403",
                request=MagicMock(),
                response=mock_response,
            ),
        )
        run = make_run(
            {
                "incidentId": "Q1QGYB805SG874",
                "fromEmail": "oncall@example.com",
                "resolution": "Restarted the service",
            }
        )
        with patch("actions.resolve_incident_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message=(
                f"Incident resolved: {INCIDENT_RESPONSE['html_url']}. "
                "Resolution note could not be added"
            ),
        )

    async def test_missing_incident_id_raises(
        self, executor: ResolveIncidentExecutor
    ) -> None:
        run = make_run({"fromEmail": "oncall@example.com"})
        with pytest.raises(MissingExecutionPropertyError, match="Field required"):
            await executor.execute(run)

    async def test_missing_from_email_raises(
        self, executor: ResolveIncidentExecutor
    ) -> None:
        run = make_run({"incidentId": "Q1QGYB805SG874"})
        with pytest.raises(MissingExecutionPropertyError, match="Field required"):
            await executor.execute(run)

    async def test_api_error_raises_update_error(
        self, executor: ResolveIncidentExecutor, mock_port_client: MagicMock
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "Incident already resolved"}
        executor.client.update_incident = AsyncMock(  # type: ignore[method-assign]
            side_effect=httpx.HTTPStatusError(
                "400",
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
            patch("actions.resolve_incident_executor.ocean") as mock_ocean,
            pytest.raises(UpdateIncidentError, match="Incident already resolved"),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

    async def test_partition_key_returns_incident_id(
        self, executor: ResolveIncidentExecutor
    ) -> None:
        run = make_run(
            {
                "incidentId": "Q1QGYB805SG874",
                "fromEmail": "oncall@example.com",
            }
        )
        assert await executor._get_partition_key(run) == "Q1QGYB805SG874"

    async def test_partition_key_returns_none_when_incident_id_missing(
        self, executor: ResolveIncidentExecutor
    ) -> None:
        run = make_run({"fromEmail": "oncall@example.com"})
        assert await executor._get_partition_key(run) is None


class TestResolveIncidentInput:
    def test_from_execution_properties_happy_path(self) -> None:
        inputs = ResolveIncidentInput.from_execution_properties(
            {
                "incidentId": "Q1QGYB805SG874",
                "fromEmail": "oncall@example.com",
                "resolution": "Restarted the service",
            }
        )

        assert inputs.to_client_kwargs() == {
            "incident_id": "Q1QGYB805SG874",
            "from_email": "oncall@example.com",
            "status": "resolved",
        }

    def test_empty_resolution_is_normalized_to_none(self) -> None:
        inputs = ResolveIncidentInput.from_execution_properties(
            {
                "incidentId": "Q1QGYB805SG874",
                "fromEmail": "oncall@example.com",
                "resolution": "   ",
            }
        )

        assert inputs.resolution is None
        assert "resolution" not in inputs.to_client_kwargs()
