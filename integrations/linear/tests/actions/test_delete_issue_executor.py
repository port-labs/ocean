from unittest.mock import MagicMock, patch

import pytest

from linear.actions.delete_issue_executor import DeleteIssueExecutor
from tests.actions.conftest import create_executor, make_run


@pytest.mark.asyncio
class TestDeleteIssueExecutor:
    async def test_happy_path(
        self,
        mock_port_client: MagicMock,
        mock_linear_client: MagicMock,
        mock_issue_mutations: MagicMock,
    ) -> None:
        executor = create_executor(DeleteIssueExecutor, mock_linear_client)
        run = make_run("delete_issue", {"issueId": "ENG-1"})
        with (
            patch("linear.actions.delete_issue_executor.ocean") as mock_ocean,
            patch(
                "linear.actions.delete_issue_executor.IssueMutations",
                return_value=mock_issue_mutations,
            ),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_issue_mutations.delete_issue.assert_awaited_once_with("ENG-1")
