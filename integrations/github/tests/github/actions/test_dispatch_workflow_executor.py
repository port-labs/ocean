"""Tests for DispatchWorkflowExecutor."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.actions.dispatch_workflow_executor import DispatchWorkflowExecutor
from github.helpers.exceptions import (
    InvalidActionParametersException,
    RepositoryDefaultBranchNotFoundException,
)
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-123",
        status=RunStatus.IN_PROGRESS,
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="dispatch_workflow",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


WORKFLOW_RUN = {
    "id": 12345,
    "html_url": "https://github.com/port-labs/ocean/actions/runs/12345",
    "repository": {
        "id": 99,
        "owner": {"id": 1},
    },
}


@pytest.fixture
def mock_rest_client() -> MagicMock:
    client = MagicMock()
    client.base_url = "https://api.github.com"
    client.make_request = AsyncMock()
    client.get_rate_limit_status = MagicMock(return_value=None)
    return client


@pytest.fixture
def mock_port_client() -> MagicMock:
    pc = MagicMock()
    pc.update_run_started = AsyncMock()
    return pc


@pytest.fixture
def executor(mock_rest_client: MagicMock) -> DispatchWorkflowExecutor:
    with patch(
        "github.actions.abstract_github_executor.create_github_client",
        return_value=mock_rest_client,
    ):
        return DispatchWorkflowExecutor()


class TestDispatchWorkflowExecutor:
    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        executor: DispatchWorkflowExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "workflow": "deploy.yml",
                "workflowInputs": {"environment": "prod"},
            }
        )

        dispatch_response = MagicMock()
        dispatch_response.json.return_value = {"workflow_run_id": 12345}
        mock_rest_client.make_request.return_value = dispatch_response

        get_resource_mock = AsyncMock(return_value=WORKFLOW_RUN)

        with (
            patch.object(
                executor, "_get_default_ref", AsyncMock(return_value="main")
            ),
            patch.object(
                executor._workflow_run_exporter,
                "get_resource",
                get_resource_mock,
            ),
            patch("github.actions.dispatch_workflow_executor.ocean") as mock_ocean,
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_rest_client.make_request.assert_awaited_once()
        call_kwargs = mock_rest_client.make_request.call_args
        assert (
            "repos/port-labs/ocean/actions/workflows/deploy.yml/dispatches"
            in call_kwargs.args[0]
        )
        assert call_kwargs.kwargs["method"] == "POST"
        assert call_kwargs.kwargs["json_data"] == {
            "ref": "main",
            "inputs": {"environment": "prod"},
            "return_run_details": True,
        }

        get_resource_mock.assert_awaited_once()
        mock_port_client.update_run_started.assert_awaited_once_with(
            run,
            WORKFLOW_RUN["html_url"],
            "gh_1_99_12345",
            extra_output={"workflowRunId": 12345},
        )

    @pytest.mark.asyncio
    async def test_uses_ref_from_workflow_inputs(
        self,
        executor: DispatchWorkflowExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "workflow": "deploy.yml",
                "workflowInputs": {"ref": "feature-branch"},
            }
        )

        dispatch_response = MagicMock()
        dispatch_response.json.return_value = {"workflow_run_id": 12345}
        mock_rest_client.make_request.return_value = dispatch_response

        with (
            patch.object(
                executor._workflow_run_exporter,
                "get_resource",
                AsyncMock(return_value=WORKFLOW_RUN),
            ),
            patch("github.actions.dispatch_workflow_executor.ocean") as mock_ocean,
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        json_data = mock_rest_client.make_request.call_args.kwargs["json_data"]
        assert json_data["ref"] == "feature-branch"
        assert "ref" not in json_data["inputs"]

    @pytest.mark.asyncio
    async def test_missing_required_params_fails(
        self,
        executor: DispatchWorkflowExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run({"org": "port-labs", "repo": "ocean"})

        with pytest.raises(
            InvalidActionParametersException,
            match="organization, repo and workflow are required",
        ):
            await executor.execute(run)

        mock_rest_client.make_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_workflow_run_id_raises(
        self,
        executor: DispatchWorkflowExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "workflow": "deploy.yml",
            }
        )

        dispatch_response = MagicMock()
        dispatch_response.json.return_value = {}
        mock_rest_client.make_request.return_value = dispatch_response

        with (
            patch.object(
                executor, "_get_default_ref", AsyncMock(return_value="main")
            ),
            patch("github.actions.dispatch_workflow_executor.ocean") as mock_ocean,
        ):
            mock_ocean.port_client = mock_port_client
            with pytest.raises(ActionExecutionError, match="Workflow run ID not found"):
                await executor.execute(run)

    @pytest.mark.asyncio
    async def test_github_http_error_raises(
        self,
        executor: DispatchWorkflowExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "workflow": "deploy.yml",
            }
        )

        request = httpx.Request(
            "POST",
            "https://api.github.com/repos/port-labs/ocean/actions/workflows/deploy.yml/dispatches",
        )
        response = httpx.Response(
            422, json={"message": "Workflow not found"}, request=request
        )
        mock_rest_client.make_request.side_effect = httpx.HTTPStatusError(
            "422", request=request, response=response
        )

        with (
            patch.object(
                executor, "_get_default_ref", AsyncMock(return_value="main")
            ),
            patch("github.actions.dispatch_workflow_executor.ocean") as mock_ocean,
        ):
            mock_ocean.port_client = mock_port_client
            with pytest.raises(
                ActionExecutionError,
                match="Error dispatching workflow: Workflow not found",
            ):
                await executor.execute(run)

    @pytest.mark.asyncio
    async def test_default_branch_not_found_raises(
        self,
        executor: DispatchWorkflowExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "workflow": "deploy.yml",
            }
        )

        with patch.object(
            executor,
            "_get_default_ref",
            AsyncMock(
                side_effect=RepositoryDefaultBranchNotFoundException(
                    "Default branch not found for repository port-labs/ocean"
                )
            ),
        ):
            with pytest.raises(
                RepositoryDefaultBranchNotFoundException,
                match="Default branch not found for repository port-labs/ocean",
            ):
                await executor.execute(run)

        mock_rest_client.make_request.assert_not_awaited()

    def test_parse_inputs(self, executor: DispatchWorkflowExecutor) -> None:
        assert executor._parse_inputs({"env": "prod"}) == {"env": "prod"}
        assert executor._parse_inputs({"count": 3}) == {"count": "3"}

    def test_action_name(self, executor: DispatchWorkflowExecutor) -> None:
        assert executor.ACTION_NAME == "dispatch_workflow"
