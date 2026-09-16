from unittest.mock import MagicMock, patch

import pytest

from linear.actions.add_issue_comment_executor import AddIssueCommentExecutor
from linear.core.mutations.issue.types import CommentCreateMutationPayload
from linear.helpers.exceptions import MissingExecutionPropertyError
from tests.actions.conftest import create_executor, make_run


@pytest.mark.asyncio
class TestAddIssueCommentExecutor:
    async def test_happy_path(
        self,
        mock_port_client: MagicMock,
        mock_linear_client: MagicMock,
        mock_issue_mutations: MagicMock,
    ) -> None:
        executor = create_executor(AddIssueCommentExecutor, mock_linear_client)
        run = make_run(
            "add_issue_comment",
            {"issueId": "ENG-1", "body": "Looks good"},
        )
        with (
            patch("linear.actions.add_issue_comment_executor.ocean") as mock_ocean,
            patch(
                "linear.actions.add_issue_comment_executor.IssueMutations",
                return_value=mock_issue_mutations,
            ),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_issue_mutations.create_comment.assert_awaited_once()
        create_payload = mock_issue_mutations.create_comment.await_args.args[0]
        assert isinstance(create_payload, CommentCreateMutationPayload)
        assert create_payload.model_dump(exclude_none=True) == {
            "issueId": "ENG-1",
            "body": "Looks good",
        }
        mock_port_client.post_run_log.assert_any_call(
            run,
            "Adding comment to issue ENG-1",
            status_label="Adding comment",
            should_raise=False,
        )
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message="Added comment comment-1 to issue ENG-1",
            status_label="Comment added",
        )

    async def test_missing_body(
        self, mock_port_client: MagicMock, mock_linear_client: MagicMock
    ) -> None:
        executor = create_executor(AddIssueCommentExecutor, mock_linear_client)
        run = make_run("add_issue_comment", {"issueId": "ENG-1"})
        with patch("linear.actions.add_issue_comment_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError):
                await executor.execute(run)
