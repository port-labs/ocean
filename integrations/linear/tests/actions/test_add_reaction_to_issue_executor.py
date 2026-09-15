from unittest.mock import MagicMock, patch

import pytest

from linear.actions.add_reaction_to_issue_executor import AddReactionToIssueExecutor
from linear.core.mutations.reaction_mutation_payload import (
    ReactionCreateMutationPayload,
)
from linear.helpers.exceptions import MissingExecutionPropertyError
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

        mock_reaction_mutations.create_reaction.assert_awaited_once()
        create_payload = mock_reaction_mutations.create_reaction.await_args.args[0]
        assert isinstance(create_payload, ReactionCreateMutationPayload)
        assert create_payload.model_dump(exclude_none=True) == {
            "issueId": "ENG-1",
            "emoji": "+1",
        }
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message="Added reaction +1 to issue ENG-1",
            status_label="Reaction added",
        )

    async def test_missing_emoji(
        self, mock_port_client: MagicMock, mock_linear_client: MagicMock
    ) -> None:
        executor = create_executor(AddReactionToIssueExecutor, mock_linear_client)
        run = make_run("add_reaction_to_issue", {"issueId": "ENG-1"})
        with patch("linear.actions.add_reaction_to_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError):
                await executor.execute(run)
