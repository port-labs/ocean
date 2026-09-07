from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from gitlab.actions.create_merge_request_executor import CreateMergeRequestExecutor
from gitlab.helpers.exceptions import (
    GitlabCreateMergeRequestError,
    MissingExecutionPropertyError,
)

MERGE_REQUEST_RESPONSE = {
    "id": 7,
    "iid": 3,
    "web_url": "https://gitlab.com/my-group/my-project/-/merge_requests/3",
    "source_branch": "feature-branch",
    "target_branch": "main",
    "title": "Add new feature",
}


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="gitlab",
            integrationInvocationType="create_merge_request",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> CreateMergeRequestExecutor:
    with patch("gitlab.actions.abstract_gitlab_executor.create_gitlab_client"):
        ex = CreateMergeRequestExecutor()
        ex.client = MagicMock()
        ex.client.create_merge_request = AsyncMock(return_value=MERGE_REQUEST_RESPONSE)
        return ex


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.report_run_completed = AsyncMock()
    client.post_run_log = AsyncMock()
    return client


@pytest.mark.asyncio
class TestCreateMergeRequestExecutor:
    async def test_happy_path(
        self, executor: CreateMergeRequestExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run(
            {
                "project": "my-group/my-project",
                "sourceBranch": "feature-branch",
                "targetBranch": "main",
                "title": "Add new feature",
            }
        )
        with patch("gitlab.actions.create_merge_request_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        executor.client.create_merge_request.assert_called_once_with(  # type: ignore[attr-defined]
            "my-group/my-project",
            "feature-branch",
            "main",
            "Add new feature",
        )
        mock_port_client.report_run_completed.assert_called_once_with(
            run,
            success=True,
            message=f"Merge request created: {MERGE_REQUEST_RESPONSE['web_url']}",
        )
        assert mock_port_client.post_run_log.await_count == 2

    async def test_missing_project_raises(
        self, executor: CreateMergeRequestExecutor
    ) -> None:
        run = make_run(
            {
                "sourceBranch": "feature-branch",
                "targetBranch": "main",
                "title": "Add new feature",
            }
        )
        with pytest.raises(MissingExecutionPropertyError, match="project is required"):
            await executor.execute(run)

    async def test_missing_source_branch_raises(
        self, executor: CreateMergeRequestExecutor
    ) -> None:
        run = make_run(
            {
                "project": "my-group/my-project",
                "targetBranch": "main",
                "title": "Add new feature",
            }
        )
        with pytest.raises(
            MissingExecutionPropertyError, match="sourceBranch is required"
        ):
            await executor.execute(run)

    async def test_missing_target_branch_raises(
        self, executor: CreateMergeRequestExecutor
    ) -> None:
        run = make_run(
            {
                "project": "my-group/my-project",
                "sourceBranch": "feature-branch",
                "title": "Add new feature",
            }
        )
        with pytest.raises(
            MissingExecutionPropertyError, match="targetBranch is required"
        ):
            await executor.execute(run)

    async def test_missing_title_raises(
        self, executor: CreateMergeRequestExecutor
    ) -> None:
        run = make_run(
            {
                "project": "my-group/my-project",
                "sourceBranch": "feature-branch",
                "targetBranch": "main",
            }
        )
        with pytest.raises(MissingExecutionPropertyError, match="title is required"):
            await executor.execute(run)

    async def test_api_error_raises_create_error(
        self, executor: CreateMergeRequestExecutor
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": "403 Forbidden"}
        executor.client.create_merge_request = AsyncMock(  # type: ignore[method-assign]
            side_effect=httpx.HTTPStatusError(
                "403",
                request=MagicMock(),
                response=mock_response,
            ),
        )
        run = make_run(
            {
                "project": "my-group/my-project",
                "sourceBranch": "feature-branch",
                "targetBranch": "main",
                "title": "Add new feature",
            }
        )
        with (
            patch("gitlab.actions.create_merge_request_executor.ocean") as mock_ocean,
            pytest.raises(GitlabCreateMergeRequestError, match="403 Forbidden"),
        ):
            mock_ocean.port_client = MagicMock()
            mock_ocean.port_client.post_run_log = AsyncMock()
            await executor.execute(run)

    async def test_incomplete_response_raises(
        self, executor: CreateMergeRequestExecutor
    ) -> None:
        executor.client.create_merge_request = AsyncMock(  # type: ignore[method-assign]
            return_value={"id": 7},
        )
        run = make_run(
            {
                "project": "my-group/my-project",
                "sourceBranch": "feature-branch",
                "targetBranch": "main",
                "title": "Add new feature",
            }
        )
        with (
            patch("gitlab.actions.create_merge_request_executor.ocean") as mock_ocean,
            pytest.raises(GitlabCreateMergeRequestError, match="empty or incomplete"),
        ):
            mock_ocean.port_client = MagicMock()
            mock_ocean.port_client.post_run_log = AsyncMock()
            await executor.execute(run)
