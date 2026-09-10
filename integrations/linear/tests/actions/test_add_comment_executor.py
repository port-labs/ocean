from unittest.mock import MagicMock, patch

import pytest

from linear.actions.add_comment_executor import AddCommentExecutor
from tests.actions.conftest import create_executor, make_run


@pytest.mark.asyncio
class TestAddCommentExecutor:
    async def test_happy_path(
        self,
        mock_port_client: MagicMock,
        mock_linear_client: MagicMock,
        mock_comment_mutations: MagicMock,
    ) -> None:
        executor = create_executor(AddCommentExecutor, mock_linear_client)
        run = make_run(
            "add_comment",
            {"issueId": "ENG-1", "body": "Looks good"},
        )
        with (
            patch("linear.actions.add_comment_executor.ocean") as mock_ocean,
            patch(
                "linear.actions.add_comment_executor.CommentMutations",
                return_value=mock_comment_mutations,
            ),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_comment_mutations.create_comment.assert_awaited_once_with(
            "ENG-1", "Looks good"
        )
