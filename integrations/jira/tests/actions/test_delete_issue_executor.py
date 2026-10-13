from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from jira.actions.delete_issue_executor import DeleteIssueExecutor, DeleteIssueInput
from jira.actions.exceptions import DeleteIssueError, MissingExecutionPropertyError


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="jira",
            integrationInvocationType="delete_issue",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> DeleteIssueExecutor:
    with patch("jira.actions.abstract_jira_executor.get_or_create_jira_client"):
        delete_issue_executor = DeleteIssueExecutor()
        delete_issue_executor.client = MagicMock()
        delete_issue_executor.client.jira_url = "https://example.atlassian.net"
        delete_issue_executor.client.is_oauth_enabled = MagicMock(return_value=False)
        delete_issue_executor.client.delete_issue = AsyncMock()
        return delete_issue_executor


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.post_run_log = AsyncMock()
    client.report_run_completed = AsyncMock()
    return client


def test_delete_issue_input_parses_camel_case_fields() -> None:
    # Arrange + Act
    action_input = DeleteIssueInput.from_execution_properties(
        {"issueKey": "PORT-42", "deleteSubtasks": True}
    )

    # Assert
    assert action_input.issue_key == "PORT-42"
    assert action_input.delete_subtasks is True


def test_delete_issue_input_defaults_delete_subtasks_to_false() -> None:
    # Arrange + Act
    action_input = DeleteIssueInput.from_execution_properties({"issueKey": "PORT-42"})

    # Assert
    assert action_input.delete_subtasks is False


def test_delete_issue_input_raises_for_missing_issue_key() -> None:
    # Act + Assert
    with pytest.raises(MissingExecutionPropertyError, match="issueKey"):
        DeleteIssueInput.from_execution_properties({})


@pytest.mark.asyncio
async def test_delete_issue_executor_happy_path(
    executor: DeleteIssueExecutor, mock_port_client: MagicMock
) -> None:
    # Arrange
    run = make_run({"issueKey": "PORT-42", "deleteSubtasks": True})

    # Act
    with (
        patch("jira.actions.delete_issue_executor.ocean") as mock_ocean,
        patch("jira.actions.abstract_jira_executor.ocean", mock_ocean),
    ):
        mock_ocean.port_client = mock_port_client
        await executor.execute(run)

    # Assert
    executor.client.delete_issue.assert_awaited_once_with(  # type: ignore[attr-defined]
        "PORT-42",
        delete_subtasks=True,
    )
    assert run.output == {
        "issueKey": "PORT-42",
        "issueUrl": "https://example.atlassian.net/browse/PORT-42",
    }
    mock_port_client.post_run_log.assert_any_call(
        run,
        "Deleting Jira issue PORT-42",
        status_label="Deleting issue",
        should_raise=False,
    )
    mock_port_client.report_run_completed.assert_called_once_with(
        run,
        success=True,
        message=("Deleted issue PORT-42: https://example.atlassian.net/browse/PORT-42"),
        status_label="Issue deleted",
    )


@pytest.mark.asyncio
async def test_delete_issue_executor_missing_required_input(
    executor: DeleteIssueExecutor, mock_port_client: MagicMock
) -> None:
    # Arrange
    run = make_run({})

    # Act + Assert
    with patch("jira.actions.delete_issue_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_port_client
        with pytest.raises(MissingExecutionPropertyError) as exc_info:
            await executor.execute(run)

    assert exc_info.value.status_label == "Invalid input"


@pytest.mark.asyncio
async def test_delete_issue_executor_upstream_http_error(
    executor: DeleteIssueExecutor, mock_port_client: MagicMock
) -> None:
    # Arrange
    response = httpx.Response(
        404,
        json={"errorMessages": ["Issue does not exist"]},
        request=httpx.Request("DELETE", "http://x"),
    )
    executor.client.delete_issue = AsyncMock(  # type: ignore[method-assign]
        side_effect=httpx.HTTPStatusError(
            "404", request=response.request, response=response
        )
    )
    run = make_run({"issueKey": "PORT-42"})

    # Act + Assert
    with patch("jira.actions.delete_issue_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_port_client
        with pytest.raises(DeleteIssueError, match="Issue does not exist") as exc_info:
            await executor.execute(run)

    assert exc_info.value.status_label == "Delete failed"


@pytest.mark.asyncio
async def test_delete_issue_executor_partition_key_uses_issue_key() -> None:
    # Arrange
    with patch("jira.actions.abstract_jira_executor.get_or_create_jira_client"):
        delete_issue_executor = DeleteIssueExecutor()
    run = make_run({"issueKey": "PORT-42"})

    # Act
    partition_key = await delete_issue_executor._get_partition_key(run)

    # Assert
    assert partition_key == "PORT-42"


@pytest.mark.asyncio
async def test_delete_issue_executor_partition_key_returns_none_without_issue_key() -> (
    None
):
    # Arrange
    with patch("jira.actions.abstract_jira_executor.get_or_create_jira_client"):
        delete_issue_executor = DeleteIssueExecutor()
    run = make_run({})

    # Act
    partition_key = await delete_issue_executor._get_partition_key(run)

    # Assert
    assert partition_key is None
