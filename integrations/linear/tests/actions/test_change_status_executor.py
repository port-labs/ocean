from unittest.mock import MagicMock, patch

import pytest

from linear.actions.change_status_executor import ChangeStatusExecutor
from linear.core.mutations.issue_mutation_payload import IssueUpdateMutationPayload
from linear.helpers.exceptions import MissingExecutionPropertyError
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
        mock_issue_mutations.update_issue.assert_awaited_once()
        update_call = mock_issue_mutations.update_issue.await_args
        assert update_call.args[0] == "ENG-1"
        assert isinstance(update_call.args[1], IssueUpdateMutationPayload)
        assert update_call.args[1].model_dump(exclude_none=True) == {
            "stateId": "state-1"
        }
        assert run.output == {
            "identifier": "ENG-1",
            "issueId": "issue-1",
            "issueUrl": "https://linear.app/test/issue/ENG-1",
        }
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message="Changed issue ENG-1 status to In Progress",
            status_label="Status changed",
        )

    async def test_missing_state(
        self, mock_port_client: MagicMock, mock_linear_client: MagicMock
    ) -> None:
        executor = create_executor(ChangeStatusExecutor, mock_linear_client)
        run = make_run("change_status", {"issueId": "ENG-1"})
        with patch("linear.actions.change_status_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError):
                await executor.execute(run)

    async def test_partition_key(self, mock_linear_client: MagicMock) -> None:
        executor = create_executor(ChangeStatusExecutor, mock_linear_client)
        run = make_run("change_status", {"issueId": "ENG-1", "stateId": "state-1"})
        assert await executor._get_partition_key(run) == "ENG-1"
        assert await executor._get_partition_key(make_run("change_status", {})) is None
