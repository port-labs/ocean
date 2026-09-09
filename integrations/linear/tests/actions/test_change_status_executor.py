from unittest.mock import MagicMock, patch

import pytest

from linear.actions.change_status_executor import ChangeStatusExecutor
from tests.actions.conftest import create_executor, make_run


@pytest.mark.asyncio
class TestChangeStatusExecutor:
    async def test_resolves_state_name(
        self,
        mock_port_client: MagicMock,
        mock_linear_client: MagicMock,
        mock_issue_mutations: MagicMock,
    ) -> None:
        executor = create_executor(ChangeStatusExecutor, mock_linear_client)
        run = make_run(
            "change_status",
            {"issueId": "ENG-1", "stateName": "In Progress"},
        )
        with (
            patch("linear.actions.change_status_executor.ocean") as mock_ocean,
            patch(
                "linear.actions.change_status_executor.IssueMutations",
                return_value=mock_issue_mutations,
            ),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_issue_mutations.resolve_state_id.assert_awaited_once_with(
            "ENG-1", "In Progress"
        )
        mock_issue_mutations.update_issue.assert_awaited_once_with(
            "ENG-1", {"stateId": "state-1"}
        )
