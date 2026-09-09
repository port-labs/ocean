from unittest.mock import MagicMock, patch

import pytest

from linear.actions.create_issue_executor import CreateIssueExecutor
from linear.helpers.exceptions import MissingExecutionPropertyError
from tests.actions.conftest import create_executor, make_run


@pytest.mark.asyncio
class TestCreateIssueExecutor:
    async def test_happy_path(
        self,
        mock_port_client: MagicMock,
        mock_linear_client: MagicMock,
        mock_issue_mutations: MagicMock,
    ) -> None:
        executor = create_executor(CreateIssueExecutor, mock_linear_client)
        run = make_run(
            "create_issue",
            {"teamId": "team-1", "title": "Bug report"},
        )
        with (
            patch("linear.actions.create_issue_executor.ocean") as mock_ocean,
            patch(
                "linear.actions.create_issue_executor.IssueMutations",
                return_value=mock_issue_mutations,
            ),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_issue_mutations.create_issue.assert_awaited_once()
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message="Created issue ENG-1: https://linear.app/test/issue/ENG-1",
        )

    async def test_missing_team_id(
        self, mock_port_client: MagicMock, mock_linear_client: MagicMock
    ) -> None:
        executor = create_executor(CreateIssueExecutor, mock_linear_client)
        run = make_run("create_issue", {"title": "Bug report"})
        with patch("linear.actions.create_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError):
                await executor.execute(run)

    async def test_missing_title(
        self, mock_port_client: MagicMock, mock_linear_client: MagicMock
    ) -> None:
        executor = create_executor(CreateIssueExecutor, mock_linear_client)
        run = make_run("create_issue", {"teamId": "team-1"})
        with patch("linear.actions.create_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError):
                await executor.execute(run)
