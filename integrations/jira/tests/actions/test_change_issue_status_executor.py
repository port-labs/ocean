from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import ValidationError
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from jira.actions.change_issue_status_executor import (
    ChangeIssueStatusExecutor,
    ChangeIssueStatusInput,
)
from jira.actions.exceptions import (
    ChangeIssueStatusError,
    MissingExecutionPropertyError,
)

TRANSITIONS_RESPONSE = {
    "transitions": [
        {
            "id": "21",
            "name": "In Progress",
            "to": {"name": "In Progress"},
        },
        {
            "id": "31",
            "name": "Done",
            "to": {"name": "Done"},
        },
    ]
}


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="jira",
            integrationInvocationType="change_issue_status",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> ChangeIssueStatusExecutor:
    with patch("jira.actions.abstract_jira_executor.get_or_create_jira_client"):
        action_executor = ChangeIssueStatusExecutor()
        action_executor.client = MagicMock()
        action_executor.client.jira_url = "https://example.atlassian.net"
        action_executor.client.is_oauth_enabled = MagicMock(return_value=False)
        action_executor.client.get_single_issue = AsyncMock(
            return_value={"fields": {"status": {"name": "To Do"}}}
        )
        action_executor.client.get_issue_transitions = AsyncMock(
            return_value=TRANSITIONS_RESPONSE
        )
        action_executor.client.transition_issue = AsyncMock(return_value=None)
        return action_executor


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.post_run_log = AsyncMock()
    client.report_run_completed = AsyncMock()
    return client


def test_from_execution_properties_parses_camel_case_fields() -> None:
    # Arrange
    execution_properties = {
        "issueKey": "PORT-42",
        "status": "In Progress",
    }

    # Act
    action_input = ChangeIssueStatusInput.from_execution_properties(
        execution_properties
    )

    # Assert
    assert action_input.issue_key == "PORT-42"
    assert action_input.status == "In Progress"


def test_from_execution_properties_raises_for_missing_required_field() -> None:
    # Arrange
    execution_properties = {"status": "Done"}

    # Act + Assert
    with pytest.raises(MissingExecutionPropertyError, match="issueKey"):
        ChangeIssueStatusInput.from_execution_properties(execution_properties)


def test_model_validate_raises_for_empty_required_field() -> None:
    # Act + Assert
    with pytest.raises(ValidationError):
        ChangeIssueStatusInput.model_validate({"issueKey": "", "status": "Done"})


@pytest.mark.asyncio
async def test_happy_path(
    executor: ChangeIssueStatusExecutor, mock_port_client: MagicMock
) -> None:
    # Arrange
    run = make_run({"issueKey": "PORT-42", "status": "In Progress"})

    # Act
    with patch("jira.actions.change_issue_status_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_port_client
        await executor.execute(run)

    # Assert
    executor.client.get_single_issue.assert_awaited_once_with(  # type: ignore[attr-defined]
        "PORT-42", fields="status"
    )
    executor.client.get_issue_transitions.assert_awaited_once_with("PORT-42")  # type: ignore[attr-defined]
    executor.client.transition_issue.assert_awaited_once_with("PORT-42", "21")  # type: ignore[attr-defined]
    assert run.output == {
        "issueKey": "PORT-42",
        "status": "In Progress",
        "issueUrl": "https://example.atlassian.net/browse/PORT-42",
    }
    mock_port_client.report_run_completed.assert_called_once_with(
        run,
        success=True,
        message=(
            "Changed issue PORT-42 to status 'In Progress': "
            "https://example.atlassian.net/browse/PORT-42"
        ),
        status_label="Status changed",
    )


@pytest.mark.asyncio
async def test_already_in_target_status(
    executor: ChangeIssueStatusExecutor, mock_port_client: MagicMock
) -> None:
    # Arrange
    executor.client.get_single_issue = AsyncMock(  # type: ignore[method-assign]
        return_value={"fields": {"status": {"name": "Done"}}}
    )
    run = make_run({"issueKey": "PORT-42", "status": "done"})

    # Act
    with patch("jira.actions.change_issue_status_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_port_client
        await executor.execute(run)

    # Assert
    executor.client.get_issue_transitions.assert_not_awaited()  # type: ignore[attr-defined]
    executor.client.transition_issue.assert_not_awaited()  # type: ignore[attr-defined]
    mock_port_client.report_run_completed.assert_called_once_with(
        run,
        success=True,
        message=(
            "Issue PORT-42 is already in status 'Done': "
            "https://example.atlassian.net/browse/PORT-42"
        ),
        status_label="Status changed",
    )


@pytest.mark.asyncio
async def test_missing_required_input(
    executor: ChangeIssueStatusExecutor, mock_port_client: MagicMock
) -> None:
    # Arrange
    run = make_run({"issueKey": "PORT-42"})

    # Act + Assert
    with patch("jira.actions.change_issue_status_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_port_client
        with pytest.raises(MissingExecutionPropertyError) as exc_info:
            await executor.execute(run)

    assert exc_info.value.status_label == "Invalid input"


@pytest.mark.asyncio
async def test_upstream_http_error(
    executor: ChangeIssueStatusExecutor, mock_port_client: MagicMock
) -> None:
    # Arrange
    response = httpx.Response(
        404,
        json={"errorMessages": ["Issue does not exist"]},
        request=httpx.Request("GET", "http://x"),
    )
    executor.client.get_single_issue = AsyncMock(  # type: ignore[method-assign]
        side_effect=httpx.HTTPStatusError(
            "404", request=response.request, response=response
        )
    )
    run = make_run({"issueKey": "PORT-42", "status": "Done"})

    # Act + Assert
    with patch("jira.actions.change_issue_status_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_port_client
        with pytest.raises(
            ChangeIssueStatusError, match="Issue does not exist"
        ) as exc_info:
            await executor.execute(run)

    assert exc_info.value.status_label == "Status change failed"


@pytest.mark.asyncio
async def test_no_matching_transition(
    executor: ChangeIssueStatusExecutor, mock_port_client: MagicMock
) -> None:
    # Arrange
    run = make_run({"issueKey": "PORT-42", "status": "Blocked"})

    # Act + Assert
    with patch("jira.actions.change_issue_status_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_port_client
        with pytest.raises(
            ChangeIssueStatusError,
            match="Available target statuses: In Progress, Done",
        ):
            await executor.execute(run)


@pytest.mark.asyncio
async def test_get_partition_key_returns_issue_key(
    executor: ChangeIssueStatusExecutor,
) -> None:
    # Arrange
    run = make_run({"issueKey": "PORT-42", "status": "Done"})

    # Act
    partition_key = await executor._get_partition_key(run)

    # Assert
    assert partition_key == "PORT-42"


@pytest.mark.asyncio
async def test_get_partition_key_returns_none_when_issue_key_missing(
    executor: ChangeIssueStatusExecutor,
) -> None:
    # Arrange
    run = make_run({"status": "Done"})

    # Act
    partition_key = await executor._get_partition_key(run)

    # Assert
    assert partition_key is None


def test_get_issue_status_name() -> None:
    # Act + Assert
    assert (
        ChangeIssueStatusExecutor._get_issue_status_name(
            {"fields": {"status": {"name": "Done"}}}
        )
        == "Done"
    )
    assert ChangeIssueStatusExecutor._get_issue_status_name({"fields": {}}) is None


def test_find_transition_id_for_status_matches_case_insensitively() -> None:
    # Arrange
    transitions = {
        "transitions": [
            {"id": "21", "to": {"name": "In Progress"}},
            {"id": "31", "to": {"name": "Done"}},
        ]
    }

    # Act + Assert
    assert (
        ChangeIssueStatusExecutor._find_transition_id_for_status(transitions, "done")
        == "31"
    )
    assert (
        ChangeIssueStatusExecutor._find_transition_id_for_status(transitions, "Unknown")
        is None
    )


def test_get_available_transition_statuses() -> None:
    # Arrange
    transitions = {
        "transitions": [
            {"to": {"name": "In Progress"}},
            {"to": {"name": "Done"}},
            {"to": {"name": "Done"}},
        ]
    }

    # Act + Assert
    assert ChangeIssueStatusExecutor._get_available_transition_statuses(
        transitions
    ) == ["In Progress", "Done"]
