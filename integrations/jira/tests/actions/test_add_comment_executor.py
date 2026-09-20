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

from jira.actions.add_comment_executor import AddCommentExecutor, AddCommentInput
from jira.actions.exceptions import AddCommentError, MissingExecutionPropertyError

ADD_COMMENT_RESPONSE = {
    "id": "10050",
    "self": "https://example.atlassian.net/rest/api/3/issue/10001/comment/10050",
}


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="jira",
            integrationInvocationType="add_comment",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> AddCommentExecutor:
    with patch("jira.actions.abstract_jira_executor.get_or_create_jira_client"):
        ex = AddCommentExecutor()
        ex.client = MagicMock()
        ex.client.jira_url = "https://example.atlassian.net"
        ex.client.is_oauth_enabled = MagicMock(return_value=False)
        ex.client.add_comment = AsyncMock(return_value=ADD_COMMENT_RESPONSE)
        return ex


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.post_run_log = AsyncMock()
    client.report_run_completed = AsyncMock()
    return client


def test_add_comment_input_from_execution_properties_parses_camel_case_fields() -> None:
    # Arrange + Act
    action_input = AddCommentInput.from_execution_properties(
        {"issueKey": "PORT-42", "comment": "Looks good to me"}
    )

    # Assert
    assert action_input.issue_key == "PORT-42"
    assert action_input.comment == "Looks good to me"


def test_add_comment_input_to_api_payload_builds_adf_body() -> None:
    # Arrange + Act
    payload = AddCommentInput.from_execution_properties(
        {"issueKey": "PORT-42", "comment": "Looks good to me"}
    ).to_api_payload()

    # Assert
    assert payload["body"]["content"][0]["content"][0]["text"] == "Looks good to me"


def test_add_comment_input_raises_for_missing_required_field() -> None:
    # Act + Assert
    with pytest.raises(MissingExecutionPropertyError, match="issueKey"):
        AddCommentInput.from_execution_properties({"comment": "Looks good to me"})


def test_add_comment_input_model_validate_raises_for_empty_required_field() -> None:
    # Act + Assert
    with pytest.raises(ValidationError):
        AddCommentInput.model_validate({"issueKey": "", "comment": "Looks good to me"})


@pytest.mark.asyncio
async def test_add_comment_happy_path(
    executor: AddCommentExecutor, mock_port_client: MagicMock
) -> None:
    # Arrange
    run = make_run({"issueKey": "PORT-42", "comment": "Looks good to me"})

    # Act
    with patch("jira.actions.add_comment_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_port_client
        await executor.execute(run)

    # Assert
    executor.client.add_comment.assert_awaited_once_with(  # type: ignore[attr-defined]
        "PORT-42",
        {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Looks good to me"}],
                    }
                ],
            }
        },
    )
    assert run.output == {
        "issueKey": "PORT-42",
        "commentId": "10050",
        "issueUrl": "https://example.atlassian.net/browse/PORT-42",
    }
    mock_port_client.report_run_completed.assert_called_once_with(
        run,
        success=True,
        message="Added comment to PORT-42: https://example.atlassian.net/browse/PORT-42",
        status_label="Comment added",
    )


@pytest.mark.asyncio
async def test_add_comment_missing_required_input(
    executor: AddCommentExecutor, mock_port_client: MagicMock
) -> None:
    # Arrange
    run = make_run({"comment": "Looks good to me"})

    # Act + Assert
    with patch("jira.actions.add_comment_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_port_client
        with pytest.raises(MissingExecutionPropertyError) as exc_info:
            await executor.execute(run)

    assert exc_info.value.status_label == "Invalid input"


@pytest.mark.asyncio
async def test_add_comment_upstream_http_error(
    executor: AddCommentExecutor, mock_port_client: MagicMock
) -> None:
    # Arrange
    response = httpx.Response(
        404,
        json={"errorMessages": ["Issue does not exist"]},
        request=httpx.Request("POST", "http://x"),
    )
    executor.client.add_comment = AsyncMock(  # type: ignore[method-assign]
        side_effect=httpx.HTTPStatusError(
            "404", request=response.request, response=response
        )
    )
    run = make_run({"issueKey": "PORT-42", "comment": "Looks good to me"})

    # Act + Assert
    with patch("jira.actions.add_comment_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_port_client
        with pytest.raises(AddCommentError, match="Issue does not exist") as exc_info:
            await executor.execute(run)

    assert exc_info.value.status_label == "Add comment failed"


@pytest.mark.asyncio
async def test_add_comment_malformed_upstream_response(
    executor: AddCommentExecutor, mock_port_client: MagicMock
) -> None:
    # Arrange
    executor.client.add_comment = AsyncMock(return_value={})  # type: ignore[method-assign]
    run = make_run({"issueKey": "PORT-42", "comment": "Looks good to me"})

    # Act + Assert
    with patch("jira.actions.add_comment_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_port_client
        with pytest.raises(AddCommentError, match="empty or incomplete"):
            await executor.execute(run)
