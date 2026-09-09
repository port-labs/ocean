from unittest.mock import MagicMock, patch

import pytest

from linear.actions.create_sub_issue_executor import CreateSubIssueExecutor
from tests.actions.conftest import create_executor, make_run


@pytest.mark.asyncio
class TestCreateSubIssueExecutor:
    async def test_resolves_team_from_parent(
        self,
        mock_port_client: MagicMock,
        mock_linear_client: MagicMock,
        mock_issue_mutations: MagicMock,
        mock_issue_exporter: MagicMock,
    ) -> None:
        executor = create_executor(CreateSubIssueExecutor, mock_linear_client)
        run = make_run(
            "create_sub_issue",
            {"parentId": "ENG-1", "title": "Sub task"},
        )
        with (
            patch("linear.actions.create_sub_issue_executor.ocean") as mock_ocean,
            patch(
                "linear.actions.create_sub_issue_executor.IssueMutations",
                return_value=mock_issue_mutations,
            ),
            patch(
                "linear.actions.create_sub_issue_executor.IssueExporter",
                return_value=mock_issue_exporter,
            ),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_issue_exporter.get_resource.assert_awaited_once()
        create_call = mock_issue_mutations.create_issue.await_args
        assert create_call is not None
        assert create_call.args[0]["teamId"] == "team-1"
        assert create_call.args[0]["parentId"] == "ENG-1"
