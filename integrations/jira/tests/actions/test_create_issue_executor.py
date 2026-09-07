from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from jira.actions.create_issue_executor import CreateIssueExecutor
from jira.actions.exceptions import CreateIssueError, MissingExecutionPropertyError

CREATE_ISSUE_RESPONSE = {
    "id": "10001",
    "key": "PORT-42",
    "self": "https://example.atlassian.net/rest/api/3/issue/10001",
}


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="jira",
            integrationInvocationType="create_issue",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> CreateIssueExecutor:
    with patch("jira.actions.abstract_jira_executor.get_or_create_jira_client"):
        ex = CreateIssueExecutor()
        ex.client = MagicMock()
        ex.client.jira_url = "https://example.atlassian.net"
        ex.client.is_oauth_enabled = MagicMock(return_value=False)
        ex.client.create_issue = AsyncMock(return_value=CREATE_ISSUE_RESPONSE)
        return ex


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.post_run_log = AsyncMock()
    client.report_run_completed = AsyncMock()
    return client


@pytest.mark.asyncio
class TestCreateIssueExecutor:
    async def test_happy_path(
        self, executor: CreateIssueExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run(
            {
                "project": "PORT",
                "issueType": "Task",
                "summary": "New task",
                "description": "Details",
                "priority": "High",
                "assigneeAccountId": "abc-123",
            }
        )
        with patch("jira.actions.create_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        executor.client.create_issue.assert_awaited_once()  # type: ignore[attr-defined]
        payload = executor.client.create_issue.await_args.args[0]  # type: ignore[attr-defined]
        assert payload["fields"]["project"] == {"key": "PORT"}
        assert payload["fields"]["issuetype"] == {"name": "Task"}
        assert payload["fields"]["summary"] == "New task"
        assert payload["fields"]["priority"] == {"name": "High"}
        assert payload["fields"]["assignee"] == {"id": "abc-123"}
        assert run.output == {
            "issueKey": "PORT-42",
            "issueId": "10001",
            "issueUrl": "https://example.atlassian.net/browse/PORT-42",
        }
        mock_port_client.report_run_completed.assert_called_once_with(
            run,
            success=True,
            message="Created issue PORT-42: https://example.atlassian.net/browse/PORT-42",
        )

    async def test_missing_required_input(
        self, executor: CreateIssueExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run({"issueType": "Task", "summary": "New task"})
        with patch("jira.actions.create_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError):
                await executor.execute(run)

    async def test_upstream_http_error(
        self, executor: CreateIssueExecutor, mock_port_client: MagicMock
    ) -> None:
        response = httpx.Response(
            400,
            json={"errorMessages": ["Issue type is required"]},
            request=httpx.Request("POST", "http://x"),
        )
        executor.client.create_issue = AsyncMock(  # type: ignore[method-assign]
            side_effect=httpx.HTTPStatusError(
                "400", request=response.request, response=response
            )
        )
        run = make_run({"project": "PORT", "issueType": "Task", "summary": "New task"})
        with patch("jira.actions.create_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(CreateIssueError, match="Issue type is required"):
                await executor.execute(run)

    async def test_malformed_upstream_response(
        self, executor: CreateIssueExecutor, mock_port_client: MagicMock
    ) -> None:
        executor.client.create_issue = AsyncMock(return_value={"id": "10001"})  # type: ignore[method-assign]
        run = make_run({"project": "PORT", "issueType": "Task", "summary": "New task"})
        with patch("jira.actions.create_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(CreateIssueError, match="empty or incomplete"):
                await executor.execute(run)
