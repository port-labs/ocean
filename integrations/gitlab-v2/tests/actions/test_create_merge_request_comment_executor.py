from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from gitlab.actions.create_merge_request_comment_executor import (
    COMMENT_CREATED_STATUS_LABEL,
    CreateMergeRequestCommentExecutor,
)
from gitlab.helpers.exceptions import (
    GitlabCreateMergeRequestCommentError,
    MissingExecutionPropertyError,
)

NOTE_RESPONSE = {
    "id": 301,
    "body": "Comment for MR",
    "noteable_iid": 11,
    "project_id": 5,
}


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="gitlab-v2",
            integrationInvocationType="create_merge_request_comment",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> CreateMergeRequestCommentExecutor:
    with patch("gitlab.actions.abstract_gitlab_executor.create_gitlab_client"):
        ex = CreateMergeRequestCommentExecutor()
        ex.client = MagicMock()
        ex.client.create_merge_request_note = AsyncMock(return_value=NOTE_RESPONSE)
        return ex


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.report_run_completed = AsyncMock()
    client.post_run_log = AsyncMock()
    return client


@pytest.mark.asyncio
class TestCreateMergeRequestCommentExecutor:
    async def test_happy_path(
        self, executor: CreateMergeRequestCommentExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run(
            {
                "project": "my-group/my-project",
                "mergeRequestIid": "11",
                "body": "Looks good to me",
            }
        )
        with patch(
            "gitlab.actions.create_merge_request_comment_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        executor.client.create_merge_request_note.assert_called_once_with(  # type: ignore[attr-defined]
            "my-group/my-project", 11, "Looks good to me"
        )
        mock_port_client.report_run_completed.assert_called_once_with(
            run,
            success=True,
            message="Created merge request comment (note ID 301)",
            status_label=COMMENT_CREATED_STATUS_LABEL,
        )
        assert run.output == {"noteId": "301", "mergeRequestIid": "11"}
        assert mock_port_client.post_run_log.await_count == 2

    async def test_missing_project_raises(
        self, executor: CreateMergeRequestCommentExecutor
    ) -> None:
        run = make_run({"mergeRequestIid": "1", "body": "hi"})
        with pytest.raises(MissingExecutionPropertyError, match="project is required"):
            await executor.execute(run)

    async def test_missing_merge_request_iid_raises(
        self, executor: CreateMergeRequestCommentExecutor
    ) -> None:
        run = make_run({"project": "my-group/my-project", "body": "hi"})
        with pytest.raises(
            MissingExecutionPropertyError, match="mergeRequestIid is required"
        ):
            await executor.execute(run)

    async def test_invalid_merge_request_iid_raises(
        self, executor: CreateMergeRequestCommentExecutor
    ) -> None:
        run = make_run(
            {
                "project": "my-group/my-project",
                "mergeRequestIid": "not-a-number",
                "body": "hi",
            }
        )
        with pytest.raises(
            MissingExecutionPropertyError,
            match="mergeRequestIid must be a valid merge request IID",
        ):
            await executor.execute(run)

    async def test_missing_body_raises(
        self, executor: CreateMergeRequestCommentExecutor
    ) -> None:
        run = make_run({"project": "my-group/my-project", "mergeRequestIid": "1"})
        with pytest.raises(MissingExecutionPropertyError, match="body is required"):
            await executor.execute(run)

    async def test_api_error_raises(
        self,
        executor: CreateMergeRequestCommentExecutor,
        mock_port_client: MagicMock,
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": "404 Not Found"}
        executor.client.create_merge_request_note = AsyncMock(  # type: ignore[method-assign]
            side_effect=httpx.HTTPStatusError(
                "404",
                request=MagicMock(),
                response=mock_response,
            )
        )
        run = make_run(
            {
                "project": "my-group/my-project",
                "mergeRequestIid": "11",
                "body": "hi",
            }
        )
        with patch(
            "gitlab.actions.create_merge_request_comment_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(GitlabCreateMergeRequestCommentError):
                await executor.execute(run)

    async def test_empty_note_response_raises(
        self, executor: CreateMergeRequestCommentExecutor, mock_port_client: MagicMock
    ) -> None:
        executor.client.create_merge_request_note = AsyncMock(return_value={})  # type: ignore[method-assign]
        run = make_run(
            {
                "project": "my-group/my-project",
                "mergeRequestIid": "11",
                "body": "hi",
            }
        )
        with patch(
            "gitlab.actions.create_merge_request_comment_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(GitlabCreateMergeRequestCommentError):
                await executor.execute(run)

        mock_port_client.report_run_completed.assert_not_called()
