"""Tests for CreateIssueExecutor."""

from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.context.ocean import ocean
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError

from github.actions.create_issue_executor import CreateIssueExecutor
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-123",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="create_issue"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="create_issue",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


def make_workflow_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-456",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationProvider="github-ocean",
            integrationInvocationType="create_issue",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


CREATED_ISSUE_RESPONSE = {
    "id": 1,
    "number": 42,
    "html_url": "https://github.com/port-labs/ocean/issues/42",
    "title": "Test issue",
}


@pytest.fixture(autouse=True)
def patched_ocean() -> Generator[MagicMock, None, None]:
    mock_client = MagicMock()
    mock_client.post_run_log = AsyncMock()
    mock_client.report_run_completed = AsyncMock()
    with patch("github.actions.create_issue_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_client
        mock_ocean.integration_config = {**ocean.integration_config}
        yield mock_ocean


@pytest.fixture
def mock_port_client(patched_ocean: MagicMock) -> MagicMock:
    return patched_ocean.port_client


@pytest.fixture
def mock_rest_client() -> MagicMock:
    client = MagicMock(spec=GithubRestClient)
    client.base_url = "https://api.github.com"
    client.make_request = AsyncMock()
    client.get_rate_limit_status = MagicMock(return_value=None)
    return client


@pytest.fixture
def executor(
    mock_rest_client: MagicMock,
) -> Generator[CreateIssueExecutor, None, None]:
    with patch(
        "github.actions.create_issue_executor.create_github_client_for_org",
        new=AsyncMock(return_value=mock_rest_client),
    ):
        yield CreateIssueExecutor()


class TestCreateIssueExecutor:
    @pytest.mark.asyncio
    async def test_create_issue_success(
        self,
        executor: CreateIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = CREATED_ISSUE_RESPONSE
        mock_rest_client.make_request.return_value = mock_response

        run = make_run({"org": "port-labs", "repo": "ocean", "title": "Test issue"})
        await executor.execute(run)

        mock_rest_client.make_request.assert_awaited_once_with(
            "https://api.github.com/repos/port-labs/ocean/issues",
            method="POST",
            json_data={"title": "Test issue"},
            ignore_default_errors=False,
        )
        mock_port_client.report_run_completed.assert_awaited_once()
        assert (
            mock_port_client.report_run_completed.await_args.kwargs["success"] is True
        )

    @pytest.mark.asyncio
    async def test_create_issue_sets_workflow_output(
        self,
        executor: CreateIssueExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = CREATED_ISSUE_RESPONSE
        mock_rest_client.make_request.return_value = mock_response

        run = make_workflow_run(
            {"org": "port-labs", "repo": "ocean", "title": "Test issue"}
        )
        await executor.execute(run)

        assert run.output == {
            "issueNumber": 42,
            "issueId": "1",
            "issueUrl": "https://github.com/port-labs/ocean/issues/42",
        }

    @pytest.mark.asyncio
    async def test_missing_title_raises(self, executor: CreateIssueExecutor) -> None:
        run = make_run({"org": "port-labs", "repo": "ocean"})
        with pytest.raises(InvalidActionParametersException):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_github_error_raises_action_execution_error(
        self,
        executor: CreateIssueExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        request = httpx.Request("POST", "https://api.github.com/repos/a/b/issues")
        response = httpx.Response(
            422,
            request=request,
            json={"message": "Validation Failed"},
        )
        mock_rest_client.make_request.side_effect = httpx.HTTPStatusError(
            "error", request=request, response=response
        )

        run = make_run({"org": "port-labs", "repo": "ocean", "title": "Test"})
        with pytest.raises(ActionExecutionError, match="Validation Failed"):
            await executor.execute(run)

    def test_action_name(self, executor: CreateIssueExecutor) -> None:
        assert executor.ACTION_NAME == "create_issue"
