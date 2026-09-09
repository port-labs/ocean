from unittest.mock import MagicMock, patch

import pytest

from linear.actions.update_issue_executor import UpdateIssueExecutor
from linear.helpers.exceptions import MissingExecutionPropertyError
from tests.actions.conftest import create_executor, make_run


@pytest.mark.asyncio
class TestUpdateIssueExecutor:
    async def test_happy_path(
        self,
        mock_port_client: MagicMock,
        mock_linear_client: MagicMock,
        mock_issue_mutations: MagicMock,
    ) -> None:
        executor = create_executor(UpdateIssueExecutor, mock_linear_client)
        run = make_run(
            "update_issue",
            {"issueId": "ENG-1", "title": "Updated title"},
        )
        with (
            patch("linear.actions.update_issue_executor.ocean") as mock_ocean,
            patch(
                "linear.actions.update_issue_executor.IssueMutations",
                return_value=mock_issue_mutations,
            ),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_issue_mutations.update_issue.assert_awaited_once_with(
            "ENG-1", {"title": "Updated title"}
        )
        mock_port_client.report_run_completed.assert_awaited_once()

    async def test_missing_update_fields(
        self, mock_port_client: MagicMock, mock_linear_client: MagicMock
    ) -> None:
        executor = create_executor(UpdateIssueExecutor, mock_linear_client)
        run = make_run("update_issue", {"issueId": "ENG-1"})
        with patch("linear.actions.update_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError):
                await executor.execute(run)

    async def test_missing_issue_id(
        self, mock_port_client: MagicMock, mock_linear_client: MagicMock
    ) -> None:
        executor = create_executor(UpdateIssueExecutor, mock_linear_client)
        run = make_run("update_issue", {"title": "Updated title"})
        with patch("linear.actions.update_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError):
                await executor.execute(run)

    async def test_partition_key(self, mock_linear_client: MagicMock) -> None:
        executor = create_executor(UpdateIssueExecutor, mock_linear_client)
        run = make_run("update_issue", {"issueId": "ENG-1", "title": "x"})
        assert await executor._get_partition_key(run) == "ENG-1"
        assert await executor._get_partition_key(make_run("update_issue", {})) is None
