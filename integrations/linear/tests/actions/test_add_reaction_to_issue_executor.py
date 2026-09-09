from unittest.mock import MagicMock, patch

import pytest

from linear.actions.add_reaction_to_issue_executor import AddReactionToIssueExecutor
from tests.actions.conftest import create_executor, make_run


@pytest.mark.asyncio
class TestAddReactionToIssueExecutor:
    async def test_happy_path(
        self,
        mock_port_client: MagicMock,
        mock_linear_client: MagicMock,
        mock_reaction_mutations: MagicMock,
    ) -> None:
        executor = create_executor(AddReactionToIssueExecutor, mock_linear_client)
        run = make_run(
            "add_reaction_to_issue",
            {"issueId": "ENG-1", "emoji": "+1"},
        )
        with (
            patch("linear.actions.add_reaction_to_issue_executor.ocean") as mock_ocean,
            patch(
                "linear.actions.add_reaction_to_issue_executor.ReactionMutations",
                return_value=mock_reaction_mutations,
            ),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_reaction_mutations.create_reaction.assert_awaited_once_with("ENG-1", "+1")
