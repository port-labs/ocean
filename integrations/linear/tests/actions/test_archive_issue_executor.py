from unittest.mock import MagicMock, patch

import pytest

from linear.actions.archive_issue_executor import ArchiveIssueExecutor
from tests.actions.conftest import create_executor, make_run


@pytest.mark.asyncio
class TestArchiveIssueExecutor:
    async def test_happy_path(
        self,
        mock_port_client: MagicMock,
        mock_linear_client: MagicMock,
        mock_issue_mutations: MagicMock,
    ) -> None:
        executor = create_executor(ArchiveIssueExecutor, mock_linear_client)
        run = make_run("archive_issue", {"issueId": "ENG-1"})
        with (
            patch("linear.actions.archive_issue_executor.ocean") as mock_ocean,
            patch(
                "linear.actions.archive_issue_executor.IssueMutations",
                return_value=mock_issue_mutations,
            ),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_issue_mutations.archive_issue.assert_awaited_once_with("ENG-1")
