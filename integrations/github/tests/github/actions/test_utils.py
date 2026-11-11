from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.actions.utils import (
    CONCLUSION_STATUS_LABELS,
    build_external_id,
    extract_error_message,
    report_workflow_run_conclusion,
)
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)


class TestBuildExternalId:
    def test_combines_owner_repo_and_run_ids(self) -> None:
        workflow_run = {
            "id": 12345,
            "repository": {"id": 99, "owner": {"id": 1}},
        }

        assert build_external_id(workflow_run) == "gh_1_99_12345"


class TestExtractErrorMessage:
    def test_uses_github_message_field(self) -> None:
        response = httpx.Response(422, json={"message": "Workflow not found"})

        assert extract_error_message(response) == "Workflow not found"

    def test_falls_back_to_raw_text_for_non_json_body(self) -> None:
        response = httpx.Response(502, text="<html>Bad gateway</html>")

        assert extract_error_message(response) == "<html>Bad gateway</html>"

    def test_falls_back_to_raw_text_for_non_object_json(self) -> None:
        response = httpx.Response(500, json=["boom"])

        assert extract_error_message(response) == '["boom"]'

    def test_serializes_non_string_message(self) -> None:
        response = httpx.Response(422, json={"message": {"detail": "nested"}})

        assert extract_error_message(response) == '{"detail": "nested"}'

    def test_falls_back_to_status_code_for_empty_body(self) -> None:
        response = httpx.Response(503, text="   ")

        assert extract_error_message(response) == "HTTP 503"


def _action_run() -> ActionRun:
    return ActionRun(
        id="run-123",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="dispatch_workflow"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="dispatch_workflow",
            integrationActionExecutionProperties={},
        ),
    )


def _workflow_node_run() -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-456",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationProvider="github-ocean",
            integrationInvocationType="dispatch_workflow",
            integrationActionExecutionProperties={},
        ),
    )


class TestReportWorkflowRunConclusion:
    def test_status_labels_are_two_words_max(self) -> None:
        for label in CONCLUSION_STATUS_LABELS.values():
            assert len(label.split()) <= 2, label

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "conclusion,expected_success,expected_label",
        [
            ("success", True, "Workflow succeeded"),
            ("failure", False, "Workflow failed"),
            ("skipped", True, "Workflow skipped"),
            ("brand_new", False, "Workflow brand_new"),
        ],
    )
    async def test_reports_conclusion_for_action_run(
        self,
        conclusion: str,
        expected_success: bool,
        expected_label: str,
    ) -> None:
        run = _action_run()
        port_client = MagicMock()
        port_client.report_run_completed = AsyncMock()

        with patch("github.actions.utils.ocean") as mock_ocean:
            mock_ocean.port_client = port_client
            await report_workflow_run_conclusion(
                run, {"conclusion": conclusion, "id": 12345}
            )

        port_client.report_run_completed.assert_awaited_once_with(
            run,
            expected_success,
            f"Workflow completed: {conclusion}",
            status_label=expected_label,
        )

    @pytest.mark.asyncio
    async def test_sets_workflow_node_run_conclusion_output(self) -> None:
        run = _workflow_node_run()
        port_client = MagicMock()
        port_client.report_run_completed = AsyncMock()

        with patch("github.actions.utils.ocean") as mock_ocean:
            mock_ocean.port_client = port_client
            await report_workflow_run_conclusion(
                run, {"conclusion": "success", "id": 12345}
            )

        assert run.output["conclusion"] == "success"
        port_client.report_run_completed.assert_awaited_once()
