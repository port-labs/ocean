from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor import (
    CONCLUSION_STATUS_LABELS,
    DispatchWorkflowWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)
from integration import GithubWorkflowRunConfig, GithubWorkflowRunSelector

WORKFLOW_RUN = {
    "id": 12345,
    "conclusion": "success",
    "html_url": "https://github.com/port-labs/ocean/actions/runs/12345",
    "repository": {
        "id": 99,
        "owner": {"id": 1},
    },
}


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-123",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="dispatch_workflow"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="dispatch_workflow",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


def make_payload(conclusion: str) -> dict[str, Any]:
    return {"workflow_run": {**WORKFLOW_RUN, "conclusion": conclusion}}


@pytest.fixture
def resource_config() -> ResourceConfig:
    return GithubWorkflowRunConfig(
        kind=ObjectKind.WORKFLOW_RUN,
        selector=GithubWorkflowRunSelector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".full_name",
                    title=".name",
                    blueprint='"githubRepository"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def mock_port_client() -> Generator[MagicMock, None, None]:
    client = MagicMock()
    client.find_run_by_external_id = AsyncMock(
        return_value=make_run({"reportWorkflowStatus": True})
    )
    client.is_run_in_progress = MagicMock(return_value=True)
    client.report_run_completed = AsyncMock()
    with patch(
        "github.webhook.webhook_processors.workflow_run."
        "dispatch_workflow_webhook_processor.ocean"
    ) as mock_ocean:
        mock_ocean.port_client = client
        yield client


@pytest.fixture
def processor(
    mock_webhook_event: WebhookEvent,
) -> DispatchWorkflowWebhookProcessor:
    return DispatchWorkflowWebhookProcessor(event=mock_webhook_event)


def test_status_labels_are_two_words_max() -> None:
    for label in CONCLUSION_STATUS_LABELS.values():
        assert len(label.split()) <= 2, label


@pytest.mark.asyncio
class TestDispatchWorkflowWebhookProcessor:
    @pytest.mark.parametrize(
        "conclusion,expected_label,expected_success",
        [
            ("success", "Workflow succeeded", True),
            ("failure", "Workflow failed", False),
            ("cancelled", "Workflow cancelled", False),
            ("timed_out", "Workflow timeout", False),
            ("skipped", "Workflow skipped", True),
            ("neutral", "Workflow neutral", True),
            ("action_required", "Action required", False),
            ("stale", "Workflow stale", False),
        ],
    )
    async def test_reports_status_label_per_conclusion(
        self,
        processor: DispatchWorkflowWebhookProcessor,
        resource_config: ResourceConfig,
        mock_port_client: MagicMock,
        conclusion: str,
        expected_label: str,
        expected_success: bool,
    ) -> None:
        await processor.handle_event(make_payload(conclusion), resource_config)

        mock_port_client.report_run_completed.assert_awaited_once()
        args, kwargs = mock_port_client.report_run_completed.await_args
        assert args[1] is expected_success
        assert kwargs["status_label"] == expected_label

    async def test_unmapped_conclusion_falls_back_to_raw_conclusion(
        self,
        processor: DispatchWorkflowWebhookProcessor,
        resource_config: ResourceConfig,
        mock_port_client: MagicMock,
    ) -> None:
        """A conclusion GitHub adds later should still yield a short label."""
        await processor.handle_event(make_payload("brand_new"), resource_config)

        label = mock_port_client.report_run_completed.await_args.kwargs["status_label"]
        assert label == "Workflow brand_new"

    @pytest.mark.parametrize(
        "in_progress,execution_properties",
        [
            (False, {"reportWorkflowStatus": True}),
            (True, {"reportWorkflowStatus": False}),
            (True, {}),
        ],
    )
    async def test_does_not_report_untracked_runs(
        self,
        processor: DispatchWorkflowWebhookProcessor,
        resource_config: ResourceConfig,
        mock_port_client: MagicMock,
        in_progress: bool,
        execution_properties: dict[str, Any],
    ) -> None:
        mock_port_client.is_run_in_progress.return_value = in_progress
        mock_port_client.find_run_by_external_id.return_value = make_run(
            execution_properties
        )

        await processor.handle_event(make_payload("success"), resource_config)

        mock_port_client.report_run_completed.assert_not_awaited()

    async def test_does_not_report_when_run_not_found(
        self,
        processor: DispatchWorkflowWebhookProcessor,
        resource_config: ResourceConfig,
        mock_port_client: MagicMock,
    ) -> None:
        mock_port_client.find_run_by_external_id.return_value = None

        await processor.handle_event(make_payload("success"), resource_config)

        mock_port_client.report_run_completed.assert_not_awaited()
