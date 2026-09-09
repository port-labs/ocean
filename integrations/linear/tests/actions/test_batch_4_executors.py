"""Tests for Linear delegate-to-agent action executor (batch 4)."""

from unittest.mock import MagicMock, patch

import pytest

from linear.actions.delegate_issue_to_agent_executor import (
    DelegateIssueToAgentExecutor,
)
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

        mock_issue_mutations.update_issue.assert_awaited_once_with(
            "ENG-1", {"delegateId": "agent-1"}
        )
