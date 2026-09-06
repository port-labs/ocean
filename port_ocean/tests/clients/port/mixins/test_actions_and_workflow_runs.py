from unittest.mock import AsyncMock, MagicMock, patch

from typing import Any

import pytest
from port_ocean.clients.port.mixins.actions_and_workflow_runs import (
    ActionsAndWorkflowRunsClientMixin,
)
from port_ocean.core.models import (
    ActionRun,
    ActionRunStatus,
    IntegrationActionInvocationPayload,
    RunStatus,
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunResult,
    WorkflowNodeRunStatus,
)

EXTERNAL_ID = "gl_42_99"


def make_action_run() -> ActionRun:
    return ActionRun(
        id="ar-1",
        status=ActionRunStatus.IN_PROGRESS,
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationActionType="trigger_pipeline",
            integrationActionExecutionProperties={},
        ),
        action=ActionRun.Action(identifier="trigger_pipeline"),
    )


def make_run() -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        node_uid="test-node-uid",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="gitlab",
            integrationInvocationType="trigger_pipeline",
            integrationActionExecutionProperties={},
        ),
        output={},
    )


@pytest.mark.parametrize(
    "raw",
    [
        {
            "identifier": "wfnr_claim",
            "nodeUid": "node-claim",
            "status": WorkflowNodeRunStatus.IN_PROGRESS,
            "config": {
                "type": "INTEGRATION_ACTION",
                "installationId": "github-actions",
                "integrationProvider": "github-ocean",
                "integrationInvocationType": "dispatch_workflow",
                "integrationActionExecutionProperties": {},
            },
        },
        {
            "identifier": "wfnr_lookup",
            "nodeUid": "node-lookup",
            "status": WorkflowNodeRunStatus.IN_PROGRESS,
            "output": {"workflowRunUrl": "https://github.com/x"},
            "node": {
                "config": {
                    "type": "INTEGRATION_ACTION",
                    "installationId": "github-actions",
                    "integrationProvider": "github-ocean",
                    "integrationInvocationType": "dispatch_workflow",
                    "integrationActionExecutionProperties": {},
                }
            },
        },
    ],
)
def test_workflow_node_run_parses_claim_and_lookup_shapes(raw: dict[str, Any]) -> None:
    run = WorkflowNodeRun.parse_obj(raw)
    assert run.action_type == "dispatch_workflow"


@pytest.fixture
def actions_client() -> ActionsAndWorkflowRunsClientMixin:
    return ActionsAndWorkflowRunsClientMixin(auth=MagicMock(), client=MagicMock())


@pytest.mark.asyncio
async def test_claim_pending_runs(
    actions_client: ActionsAndWorkflowRunsClientMixin,
) -> None:
    action_runs = [MagicMock() for _ in range(3)]
    with (
        patch.object(
            actions_client,
            "claim_pending_action_runs",
            AsyncMock(return_value=action_runs),
        ),
        patch.object(
            actions_client,
            "claim_pending_wf_node_runs",
            AsyncMock(),
        ) as mock_workflow,
    ):
        assert (
            await actions_client.claim_pending_runs(limit=3, visibility_timeout_ms=1)
            == action_runs
        )
        mock_workflow.assert_not_awaited()

    action_run, wf_run = MagicMock(), MagicMock()
    with (
        patch.object(
            actions_client,
            "claim_pending_action_runs",
            AsyncMock(return_value=[action_run]),
        ) as mock_actions,
        patch.object(
            actions_client,
            "claim_pending_wf_node_runs",
            AsyncMock(return_value=[wf_run]),
        ) as mock_workflow,
    ):
        assert await actions_client.claim_pending_runs(
            limit=10, visibility_timeout_ms=1
        ) == [wf_run, action_run]
        assert mock_workflow.await_args is not None
        assert mock_actions.await_args is not None
        assert mock_workflow.await_args.kwargs["limit"] == 10
        assert mock_actions.await_args.kwargs["limit"] == 9

    action_run, wf_run = MagicMock(), MagicMock()
    with (
        patch.object(
            actions_client,
            "claim_pending_action_runs",
            AsyncMock(return_value=[action_run]),
        ),
        patch.object(
            actions_client,
            "claim_pending_wf_node_runs",
            AsyncMock(return_value=[wf_run]),
        ),
    ):
        assert await actions_client.claim_pending_runs(
            limit=5, visibility_timeout_ms=1
        ) == [action_run, wf_run]


@pytest.mark.asyncio
class TestWorkflowNodeRunOutputPreservation:
    async def test_update_run_started_sets_run_output(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_run()
        with patch.object(
            actions_client, "patch_wf_node_run", AsyncMock()
        ) as mock_patch:
            await actions_client.update_run_started(
                run,
                "https://gitlab.example/pipelines/99",
                EXTERNAL_ID,
            )

        assert run.output == {"workflowRunUrl": "https://gitlab.example/pipelines/99"}
        mock_patch.assert_awaited_once_with(
            run.id,
            {
                "status": WorkflowNodeRunStatus.IN_PROGRESS,
                "externalRunId": EXTERNAL_ID,
                "output": {"workflowRunUrl": "https://gitlab.example/pipelines/99"},
                "links": ["https://gitlab.example/pipelines/99"],
            },
        )

    async def test_report_run_completed_preserves_output(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_run()
        run.output = {"workflowRunUrl": "https://gitlab.example/pipelines/99"}
        with (
            patch.object(
                actions_client, "patch_wf_node_run", AsyncMock()
            ) as mock_patch,
            patch.object(actions_client, "post_wf_node_run_logs", AsyncMock()),
        ):
            await actions_client.report_run_completed(run, True, "done")

        mock_patch.assert_awaited_once_with(
            run.id,
            {
                "status": WorkflowNodeRunStatus.COMPLETED,
                "result": WorkflowNodeRunResult.SUCCESS,
                "output": {"workflowRunUrl": "https://gitlab.example/pipelines/99"},
            },
            should_raise=False,
        )

    async def test_report_run_completed_failure_preserves_output(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_run()
        run.output = {"workflowRunUrl": "https://gitlab.example/pipelines/99"}
        with (
            patch.object(
                actions_client, "patch_wf_node_run", AsyncMock()
            ) as mock_patch,
            patch.object(actions_client, "post_wf_node_run_logs", AsyncMock()),
        ):
            await actions_client.report_run_completed(
                run, success=False, message="pipeline failed"
            )

        mock_patch.assert_awaited_once_with(
            run.id,
            {
                "status": WorkflowNodeRunStatus.COMPLETED,
                "result": WorkflowNodeRunResult.FAILED,
                "output": {"workflowRunUrl": "https://gitlab.example/pipelines/99"},
            },
            should_raise=False,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_label,expected_body",
    [
        (None, {"message": "hello"}),
        ("Pipeline running", {"message": "hello", "statusLabel": "Pipeline running"}),
    ],
)
async def test_post_action_run_log_body(
    status_label: str | None, expected_body: dict[str, str]
) -> None:
    auth = MagicMock()
    auth.api_url = "https://api.port.io/v1"
    auth.headers = AsyncMock(return_value={})
    client = MagicMock()
    client.post = AsyncMock(return_value=MagicMock(is_error=False))
    actions_client = ActionsAndWorkflowRunsClientMixin(auth=auth, client=client)

    await actions_client.post_action_run_log("ar-1", "hello", status_label=status_label)

    assert client.post.await_args is not None
    assert client.post.await_args.kwargs["json"] == expected_body


@pytest.mark.asyncio
class TestActionRunStatusLabel:
    async def test_post_run_log_forwards_status_label(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_action_run()
        with patch.object(
            actions_client, "post_action_run_log", AsyncMock()
        ) as mock_log:
            await actions_client.post_run_log(
                run, "Triggering pipeline", status_label="Triggering pipeline"
            )

        mock_log.assert_awaited_once_with(
            run.id, "Triggering pipeline", status_label="Triggering pipeline"
        )

    async def test_update_run_started_includes_status_label(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_action_run()
        with patch.object(
            actions_client, "patch_action_run", AsyncMock()
        ) as mock_patch:
            await actions_client.update_run_started(
                run,
                "https://gitlab.example/pipelines/99",
                EXTERNAL_ID,
                status_label="Pipeline running",
            )

        mock_patch.assert_awaited_once_with(
            run.id,
            {
                "link": "https://gitlab.example/pipelines/99",
                "externalRunId": EXTERNAL_ID,
                "statusLabel": "Pipeline running",
            },
        )

    async def test_update_run_started_omits_absent_status_label(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_action_run()
        with patch.object(
            actions_client, "patch_action_run", AsyncMock()
        ) as mock_patch:
            await actions_client.update_run_started(
                run, "https://gitlab.example/pipelines/99", EXTERNAL_ID
            )

        mock_patch.assert_awaited_once_with(
            run.id,
            {
                "link": "https://gitlab.example/pipelines/99",
                "externalRunId": EXTERNAL_ID,
            },
        )

    async def test_report_run_completed_includes_status_label(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_action_run()
        with (
            patch.object(actions_client, "patch_action_run", AsyncMock()) as mock_patch,
            patch.object(actions_client, "post_action_run_log", AsyncMock()),
        ):
            await actions_client.report_run_completed(
                run, success=False, message="boom", status_label="Pipeline failed"
            )

        mock_patch.assert_awaited_once_with(
            run.id,
            {"status": RunStatus.FAILURE, "statusLabel": "Pipeline failed"},
            should_raise=False,
        )

    async def test_report_run_completed_omits_absent_status_label(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_action_run()
        with (
            patch.object(actions_client, "patch_action_run", AsyncMock()) as mock_patch,
            patch.object(actions_client, "post_action_run_log", AsyncMock()),
        ):
            await actions_client.report_run_completed(run, success=True)

        mock_patch.assert_awaited_once_with(
            run.id, {"status": RunStatus.SUCCESS}, should_raise=False
        )


@pytest.mark.asyncio
class TestWorkflowNodeRunStatusLabel:
    """Workflow node runs take the label on the run, not on the log entry."""

    async def test_post_run_log_patches_status_label_onto_the_run(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_run()
        with (
            patch.object(
                actions_client, "post_wf_node_run_logs", AsyncMock()
            ) as mock_logs,
            patch.object(
                actions_client, "patch_wf_node_run", AsyncMock()
            ) as mock_patch,
        ):
            await actions_client.post_run_log(
                run,
                "Triggering pipeline",
                status_label="Triggering pipeline",
            )

        assert mock_logs.await_args is not None
        logs = mock_logs.await_args.args[1]
        assert [(log.level, log.message) for log in logs] == [
            ("INFO", "Triggering pipeline")
        ]
        mock_patch.assert_awaited_once_with(
            run.id, {"statusLabel": "Triggering pipeline"}, should_raise=False
        )

    async def test_post_run_log_skips_patch_without_status_label(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_run()
        with (
            patch.object(actions_client, "post_wf_node_run_logs", AsyncMock()),
            patch.object(
                actions_client, "patch_wf_node_run", AsyncMock()
            ) as mock_patch,
        ):
            await actions_client.post_run_log(run, "Triggering pipeline")

        mock_patch.assert_not_awaited()

    async def test_update_run_started_includes_status_label(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_run()
        with patch.object(
            actions_client, "patch_wf_node_run", AsyncMock()
        ) as mock_patch:
            await actions_client.update_run_started(
                run,
                "https://gitlab.example/pipelines/99",
                EXTERNAL_ID,
                status_label="Pipeline running",
            )

        mock_patch.assert_awaited_once_with(
            run.id,
            {
                "status": WorkflowNodeRunStatus.IN_PROGRESS,
                "externalRunId": EXTERNAL_ID,
                "output": {"workflowRunUrl": "https://gitlab.example/pipelines/99"},
                "links": ["https://gitlab.example/pipelines/99"],
                "statusLabel": "Pipeline running",
            },
        )

    async def test_report_run_completed_includes_status_label(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_run()
        run.output = {"workflowRunUrl": "https://gitlab.example/pipelines/99"}
        with (
            patch.object(
                actions_client, "patch_wf_node_run", AsyncMock()
            ) as mock_patch,
            patch.object(actions_client, "post_wf_node_run_logs", AsyncMock()),
        ):
            await actions_client.report_run_completed(
                run, success=True, status_label="Pipeline succeeded"
            )

        mock_patch.assert_awaited_once_with(
            run.id,
            {
                "status": WorkflowNodeRunStatus.COMPLETED,
                "result": WorkflowNodeRunResult.SUCCESS,
                "output": {"workflowRunUrl": "https://gitlab.example/pipelines/99"},
                "statusLabel": "Pipeline succeeded",
            },
            should_raise=False,
        )
