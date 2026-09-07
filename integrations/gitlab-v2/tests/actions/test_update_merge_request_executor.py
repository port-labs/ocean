from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from gitlab.actions.update_merge_request_executor import UpdateMergeRequestExecutor
from gitlab.helpers.exceptions import (
    GitlabUpdateMergeRequestError,
    MissingExecutionPropertyError,
)

MR_RESPONSE = {
    "iid": 18,
    "web_url": "https://gitlab.com/my-group/my-project/-/merge_requests/18",
}


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="gitlab",
            integrationInvocationType="update_merge_request",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> UpdateMergeRequestExecutor:
    with patch("gitlab.actions.abstract_gitlab_executor.create_gitlab_client"):
        ex = UpdateMergeRequestExecutor()
        ex.client = MagicMock()
        ex.client.update_merge_request = AsyncMock(return_value=MR_RESPONSE)
        return ex


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.update_run_started = AsyncMock()
    client.report_run_completed = AsyncMock()
    client.post_run_log = AsyncMock()
    return client


@pytest.mark.asyncio
class TestUpdateMergeRequestExecutor:
    async def test_happy_path(
        self, executor: UpdateMergeRequestExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run(
            {
                "id": "my-group/my-project",
                "mergeRequestIid": "18",
                "title": "New title",
                "description": "Updated description",
                "stateEvent": "close",
                "targetBranch": "main",
                "assigneeIds": [1, "2"],
                "reviewerIds": ["3"],
            }
        )
        with patch("gitlab.actions.update_merge_request_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        executor.client.update_merge_request.assert_called_once_with(  # type: ignore[attr-defined]
            "my-group/my-project",
            "18",
            {
                "title": "New title",
                "description": "Updated description",
                "state_event": "close",
                "target_branch": "main",
                "assignee_ids": [1, 2],
                "reviewer_ids": [3],
            },
        )
        mock_port_client.report_run_completed.assert_called_once_with(
            run,
            success=True,
            message=f"Updated merge request: {MR_RESPONSE['web_url']}",
        )
        mock_port_client.update_run_started.assert_not_called()

    async def test_missing_id_raises(
        self, executor: UpdateMergeRequestExecutor
    ) -> None:
        run = make_run({"mergeRequestIid": "18", "title": "x"})
        with pytest.raises(
            MissingExecutionPropertyError, match=r"id\s+field required"
        ):
            await executor.execute(run)

    async def test_missing_merge_request_iid_raises(
        self, executor: UpdateMergeRequestExecutor
    ) -> None:
        run = make_run({"id": "my-group/my-project", "title": "x"})
        with pytest.raises(
            MissingExecutionPropertyError,
            match=r"mergeRequestIid\s+field required",
        ):
            await executor.execute(run)

    async def test_no_update_fields_raises(
        self, executor: UpdateMergeRequestExecutor
    ) -> None:
        run = make_run({"id": "my-group/my-project", "mergeRequestIid": "18"})
        with pytest.raises(
            MissingExecutionPropertyError, match="At least one of title"
        ):
            await executor.execute(run)

    async def test_invalid_state_event_raises(
        self, executor: UpdateMergeRequestExecutor
    ) -> None:
        run = make_run(
            {
                "id": "my-group/my-project",
                "mergeRequestIid": "18",
                "stateEvent": "merge",
            }
        )
        with pytest.raises(
            MissingExecutionPropertyError, match="stateEvent must be one of"
        ):
            await executor.execute(run)

    async def test_invalid_assignee_ids_raises(
        self, executor: UpdateMergeRequestExecutor
    ) -> None:
        run = make_run(
            {
                "id": "my-group/my-project",
                "mergeRequestIid": "18",
                "assigneeIds": "1,2",
            }
        )
        with pytest.raises(
            MissingExecutionPropertyError, match="assigneeIds must be an array"
        ):
            await executor.execute(run)

    async def test_invalid_reviewer_id_item_raises(
        self, executor: UpdateMergeRequestExecutor
    ) -> None:
        run = make_run(
            {
                "id": "my-group/my-project",
                "mergeRequestIid": "18",
                "reviewerIds": ["abc"],
            }
        )
        with pytest.raises(
            MissingExecutionPropertyError, match="reviewerIds must contain integer"
        ):
            await executor.execute(run)

    async def test_api_error_raises(self, executor: UpdateMergeRequestExecutor) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": "404 Not Found"}
        executor.client.update_merge_request = AsyncMock(  # type: ignore[method-assign]
            side_effect=httpx.HTTPStatusError(
                "404",
                request=MagicMock(),
                response=mock_response,
            ),
        )
        run = make_run(
            {"id": "my-group/my-project", "mergeRequestIid": "18", "title": "x"}
        )
        with (
            patch("gitlab.actions.update_merge_request_executor.ocean") as mock_ocean,
            pytest.raises(GitlabUpdateMergeRequestError, match="404 Not Found"),
        ):
            mock_ocean.port_client = MagicMock()
            mock_ocean.port_client.post_run_log = AsyncMock()
            await executor.execute(run)

    async def test_incomplete_response_raises(
        self, executor: UpdateMergeRequestExecutor
    ) -> None:
        executor.client.update_merge_request = AsyncMock(  # type: ignore[method-assign]
            return_value={"iid": 18},
        )
        run = make_run(
            {"id": "my-group/my-project", "mergeRequestIid": "18", "title": "x"}
        )
        with (
            patch("gitlab.actions.update_merge_request_executor.ocean") as mock_ocean,
            pytest.raises(GitlabUpdateMergeRequestError, match="empty or incomplete"),
        ):
            mock_ocean.port_client = MagicMock()
            mock_ocean.port_client.post_run_log = AsyncMock()
            mock_ocean.port_client.report_run_completed = AsyncMock()
            await executor.execute(run)

    async def test_empty_assignee_ids_unassigns(
        self, executor: UpdateMergeRequestExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run(
            {
                "id": "my-group/my-project",
                "mergeRequestIid": "18",
                "assigneeIds": [],
            }
        )
        with patch("gitlab.actions.update_merge_request_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        executor.client.update_merge_request.assert_called_once_with(  # type: ignore[attr-defined]
            "my-group/my-project",
            "18",
            {"assignee_ids": []},
        )

    async def test_partition_key(self, executor: UpdateMergeRequestExecutor) -> None:
        run = make_run({"id": "my-group/my-project", "mergeRequestIid": "18"})
        assert await executor._get_partition_key(run) == "my-group/my-project/18"

    async def test_partition_key_missing_inputs_returns_none(
        self, executor: UpdateMergeRequestExecutor
    ) -> None:
        assert await executor._get_partition_key(make_run({})) is None
        assert (
            await executor._get_partition_key(make_run({"id": "my-group/my-project"}))
            is None
        )
