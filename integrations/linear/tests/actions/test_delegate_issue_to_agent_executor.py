from unittest.mock import MagicMock, patch

import pytest

from linear.actions.delegate_issue_to_agent_executor import (
    DelegateIssueToAgentExecutor,
)
from linear.core.mutations.issue_mutation_payload import IssueUpdateMutationPayload
from linear.helpers.exceptions import MissingExecutionPropertyError
from tests.actions.conftest import create_executor, make_run


@pytest.mark.asyncio
class TestDelegateIssueToAgentExecutor:
    async def test_happy_path(
        self,
        mock_port_client: MagicMock,
        mock_linear_client: MagicMock,
        mock_issue_mutations: MagicMock,
    ) -> None:
        executor = create_executor(DelegateIssueToAgentExecutor, mock_linear_client)
        run = make_run(
            "delegate_issue_to_agent",
            {"issueId": "ENG-1", "delegateId": "agent-1"},
        )
        with (
            patch(
                "linear.actions.delegate_issue_to_agent_executor.ocean"
            ) as mock_ocean,
            patch(
                "linear.actions.delegate_issue_to_agent_executor.IssueMutations",
                return_value=mock_issue_mutations,
            ),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_issue_mutations.update_issue.assert_awaited_once()
        update_call = mock_issue_mutations.update_issue.await_args
        assert update_call.args[0] == "ENG-1"
        assert isinstance(update_call.args[1], IssueUpdateMutationPayload)
        assert update_call.args[1].model_dump(exclude_none=True) == {
            "delegateId": "agent-1"
        }
        assert run.output == {
            "identifier": "ENG-1",
            "issueId": "issue-1",
            "issueUrl": "https://linear.app/test/issue/ENG-1",
        }
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message="Delegated issue ENG-1 to agent agent-1",
            status_label="Issue delegated",
        )

    async def test_missing_delegate_id(
        self, mock_port_client: MagicMock, mock_linear_client: MagicMock
    ) -> None:
        executor = create_executor(DelegateIssueToAgentExecutor, mock_linear_client)
        run = make_run("delegate_issue_to_agent", {"issueId": "ENG-1"})
        with patch(
            "linear.actions.delegate_issue_to_agent_executor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError):
                await executor.execute(run)

    async def test_partition_key(self, mock_linear_client: MagicMock) -> None:
        executor = create_executor(DelegateIssueToAgentExecutor, mock_linear_client)
        run = make_run(
            "delegate_issue_to_agent", {"issueId": "ENG-1", "delegateId": "agent-1"}
        )
        assert await executor._get_partition_key(run) == "ENG-1"
        assert (
            await executor._get_partition_key(make_run("delegate_issue_to_agent", {}))
            is None
        )
