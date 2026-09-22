from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from jira.actions.exceptions import MissingExecutionPropertyError, UpdateIssueError
from jira.actions.update_issue_executor import UpdateIssueExecutor, UpdateIssueInput


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="jira",
            integrationInvocationType="update_issue",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> UpdateIssueExecutor:
    with patch("jira.actions.abstract_jira_executor.get_or_create_jira_client"):
        ex = UpdateIssueExecutor()
        ex.client = MagicMock()
        ex.client.jira_url = "https://example.atlassian.net"
        ex.client.is_oauth_enabled = MagicMock(return_value=False)
        ex.client.update_issue = AsyncMock()
        return ex


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.post_run_log = AsyncMock()
    client.report_run_completed = AsyncMock()
    return client


def test_update_issue_input_from_execution_properties_parses_camel_case_fields() -> (
    None
):
    # Arrange + Act
    action_input = UpdateIssueInput.from_execution_properties(
        {
            "issueKey": "PORT-42",
            "summary": "Updated summary",
            "description": "Updated description",
            "priority": "High",
            "assigneeAccountId": "abc-123",
        }
    )

    # Assert
    assert action_input.issue_key == "PORT-42"
    assert action_input.summary == "Updated summary"
    assert action_input.description == "Updated description"
    assert action_input.priority == "High"
    assert action_input.assignee_account_id == "abc-123"


def test_update_issue_input_to_api_payload_includes_provided_fields() -> None:
    # Arrange + Act
    payload = UpdateIssueInput.from_execution_properties(
        {
            "issueKey": "PORT-42",
            "summary": "Updated summary",
            "priority": "High",
            "fields": {"labels": ["backend"]},
        }
    ).to_api_payload()

    # Assert
    assert payload["fields"]["summary"] == "Updated summary"
    assert payload["fields"]["priority"] == {"name": "High"}
    assert payload["fields"]["labels"] == ["backend"]


def test_update_issue_input_to_api_payload_skips_empty_optional_fields() -> None:
    # Arrange + Act
    payload = UpdateIssueInput.from_execution_properties(
        {
            "issueKey": "PORT-42",
            "summary": "Updated summary",
            "description": "",
            "priority": "",
            "assigneeAccountId": "",
        }
    ).to_api_payload()

    # Assert
    assert payload["fields"] == {"summary": "Updated summary"}


def test_update_issue_input_raises_when_no_fields_provided() -> None:
    # Act + Assert
    with pytest.raises(
        MissingExecutionPropertyError, match="At least one field must be provided"
    ):
        UpdateIssueInput.from_execution_properties(
            {"issueKey": "PORT-42"}
        ).to_api_payload()


def test_update_issue_input_raises_for_missing_issue_key() -> None:
    # Act + Assert
    with pytest.raises(MissingExecutionPropertyError, match="issueKey"):
        UpdateIssueInput.from_execution_properties({"summary": "Updated summary"})


@pytest.mark.asyncio
async def test_update_issue_executor_happy_path(
    executor: UpdateIssueExecutor, mock_port_client: MagicMock
) -> None:
    # Arrange
    run = make_run(
        {
            "issueKey": "PORT-42",
            "summary": "Updated summary",
            "priority": "High",
        }
    )

    # Act
    with (
        patch("jira.actions.update_issue_executor.ocean") as mock_ocean,
        patch("jira.actions.abstract_jira_executor.ocean", mock_ocean),
    ):
        mock_ocean.port_client = mock_port_client
        await executor.execute(run)

    # Assert
    executor.client.update_issue.assert_awaited_once_with(  # type: ignore[attr-defined]
        "PORT-42",
        {
            "fields": {
                "summary": "Updated summary",
                "priority": {"name": "High"},
            }
        },
    )
    assert run.output == {
        "issueKey": "PORT-42",
        "updatedFields": ["summary", "priority"],
        "issueUrl": "https://example.atlassian.net/browse/PORT-42",
    }
    mock_port_client.report_run_completed.assert_called_once_with(
        run,
        success=True,
        message="Updated issue PORT-42: https://example.atlassian.net/browse/PORT-42",
        status_label="Issue updated",
    )


@pytest.mark.asyncio
async def test_update_issue_executor_raises_for_upstream_http_error(
    executor: UpdateIssueExecutor, mock_port_client: MagicMock
) -> None:
    # Arrange
    response = httpx.Response(
        400,
        json={"errorMessages": ["Field 'summary' cannot be set"]},
        request=httpx.Request("PUT", "http://x"),
    )
    executor.client.update_issue = AsyncMock(  # type: ignore[method-assign]
        side_effect=httpx.HTTPStatusError(
            "400", request=response.request, response=response
        )
    )
    run = make_run({"issueKey": "PORT-42", "summary": "Updated summary"})

    # Act + Assert
    with (
        patch("jira.actions.update_issue_executor.ocean") as mock_ocean,
        patch("jira.actions.abstract_jira_executor.ocean", mock_ocean),
    ):
        mock_ocean.port_client = mock_port_client
        with pytest.raises(
            UpdateIssueError, match="Field 'summary' cannot be set"
        ) as exc_info:
            await executor.execute(run)

    assert exc_info.value.status_label == "Update failed"


@pytest.mark.asyncio
async def test_update_issue_executor_partition_key_returns_issue_key(
    executor: UpdateIssueExecutor,
) -> None:
    # Arrange
    run = make_run({"issueKey": "PORT-42", "summary": "Updated summary"})

    # Act + Assert
    assert await executor._get_partition_key(run) == "PORT-42"


@pytest.mark.asyncio
async def test_update_issue_executor_partition_key_returns_none_without_issue_key(
    executor: UpdateIssueExecutor,
) -> None:
    # Arrange
    run = make_run({"summary": "Updated summary"})

    # Act + Assert
    assert await executor._get_partition_key(run) is None
