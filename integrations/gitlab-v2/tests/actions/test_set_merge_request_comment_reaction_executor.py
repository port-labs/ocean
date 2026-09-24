from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from gitlab.actions.set_merge_request_comment_reaction_executor import (
    REACTION_UPDATED_STATUS_LABEL,
    SetMergeRequestCommentReactionExecutor,
)
from gitlab.clients.gitlab_client import AwardEmoji
from gitlab.helpers.exceptions import (
    GitlabSetMergeRequestCommentReactionError,
    MissingExecutionPropertyError,
)

AWARD_RESPONSE = {
    "id": 88,
    "name": "thumbsup",
    "user": {"id": 1},
}


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="gitlab-v2",
            integrationInvocationType="set_merge_request_comment_reaction",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> SetMergeRequestCommentReactionExecutor:
    with patch("gitlab.actions.abstract_gitlab_executor.create_gitlab_client"):
        ex = SetMergeRequestCommentReactionExecutor()
        ex.client = MagicMock()
        ex.client.award_merge_request_note_emoji = AsyncMock(
            return_value=AWARD_RESPONSE
        )
        ex.client.list_merge_request_note_award_emojis = AsyncMock(
            return_value=[AwardEmoji(id=88, name="thumbsup")]
        )
        ex.client.revoke_merge_request_note_award_emoji = AsyncMock(return_value={})
        return ex


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.report_run_completed = AsyncMock()
    client.post_run_log = AsyncMock()
    return client


@pytest.mark.asyncio
class TestSetMergeRequestCommentReactionExecutor:
    async def test_add_reaction_happy_path(
        self,
        executor: SetMergeRequestCommentReactionExecutor,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "project": "my-group/my-project",
                "mergeRequestIid": "11",
                "noteId": "301",
                "name": "thumbsup",
            }
        )
        with patch(
            "gitlab.actions.set_merge_request_comment_reaction_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        executor.client.award_merge_request_note_emoji.assert_called_once_with(  # type: ignore[attr-defined]
            "my-group/my-project", 11, 301, "thumbsup"
        )
        assert run.output == {
            "noteId": "301",
            "mergeRequestIid": "11",
            "name": "thumbsup",
            "removed": False,
            "awardId": "88",
        }
        mock_port_client.report_run_completed.assert_called_once()
        assert (
            mock_port_client.report_run_completed.call_args.kwargs["status_label"]
            == REACTION_UPDATED_STATUS_LABEL
        )

    async def test_remove_reaction_happy_path(
        self,
        executor: SetMergeRequestCommentReactionExecutor,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "project": "my-group/my-project",
                "mergeRequestIid": "11",
                "noteId": "301",
                "name": "thumbsup",
                "removeReaction": True,
            }
        )
        with patch(
            "gitlab.actions.set_merge_request_comment_reaction_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        executor.client.list_merge_request_note_award_emojis.assert_called_once_with(  # type: ignore[attr-defined]
            "my-group/my-project", 11, 301
        )
        executor.client.revoke_merge_request_note_award_emoji.assert_called_once_with(  # type: ignore[attr-defined]
            "my-group/my-project", 11, 301, 88
        )
        assert run.output == {
            "noteId": "301",
            "mergeRequestIid": "11",
            "name": "thumbsup",
            "removed": True,
        }

    async def test_missing_project_raises(
        self, executor: SetMergeRequestCommentReactionExecutor
    ) -> None:
        run = make_run({"mergeRequestIid": "1", "noteId": "2", "name": "thumbsup"})
        with pytest.raises(MissingExecutionPropertyError, match="project"):
            await executor.execute(run)

    async def test_invalid_note_id_raises(
        self, executor: SetMergeRequestCommentReactionExecutor
    ) -> None:
        run = make_run(
            {"project": "p", "mergeRequestIid": "1", "noteId": "abc", "name": "x"}
        )
        with pytest.raises(MissingExecutionPropertyError, match="noteId"):
            await executor.execute(run)

    async def test_remove_when_not_found_raises(
        self,
        executor: SetMergeRequestCommentReactionExecutor,
        mock_port_client: MagicMock,
    ) -> None:
        executor.client.list_merge_request_note_award_emojis = AsyncMock(return_value=[])  # type: ignore[method-assign]
        run = make_run(
            {
                "project": "p",
                "mergeRequestIid": "1",
                "noteId": "2",
                "name": "thumbsup",
                "removeReaction": True,
            }
        )
        with patch(
            "gitlab.actions.set_merge_request_comment_reaction_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(GitlabSetMergeRequestCommentReactionError):
                await executor.execute(run)

    async def test_api_error_on_add_raises(
        self,
        executor: SetMergeRequestCommentReactionExecutor,
        mock_port_client: MagicMock,
    ) -> None:
        response = httpx.Response(
            403, request=httpx.Request("POST", "https://gitlab.com")
        )
        executor.client.award_merge_request_note_emoji = AsyncMock(  # type: ignore[method-assign]
            side_effect=httpx.HTTPStatusError(
                "forbidden", request=response.request, response=response
            )
        )
        run = make_run(
            {
                "project": "p",
                "mergeRequestIid": "1",
                "noteId": "2",
                "name": "thumbsup",
            }
        )
        with patch(
            "gitlab.actions.set_merge_request_comment_reaction_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(GitlabSetMergeRequestCommentReactionError):
                await executor.execute(run)
