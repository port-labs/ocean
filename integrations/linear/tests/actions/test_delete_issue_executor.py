from unittest.mock import MagicMock, patch

import pytest

from linear.actions.delete_issue_executor import DeleteIssueExecutor
from linear.helpers.exceptions import MissingExecutionPropertyError
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
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message="Deleted issue ENG-1",
            status_label="Issue deleted",
        )

    async def test_missing_issue_id(
        self, mock_port_client: MagicMock, mock_linear_client: MagicMock
    ) -> None:
        executor = create_executor(DeleteIssueExecutor, mock_linear_client)
        run = make_run("delete_issue", {})
        with patch("linear.actions.delete_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError):
                await executor.execute(run)

    async def test_partition_key(self, mock_linear_client: MagicMock) -> None:
        executor = create_executor(DeleteIssueExecutor, mock_linear_client)
        run = make_run("delete_issue", {"issueId": "ENG-1"})
        assert await executor._get_partition_key(run) == "ENG-1"
        assert await executor._get_partition_key(make_run("delete_issue", {})) is None
