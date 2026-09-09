"""Tests for Linear issue create/update action executors (batch 1)."""

from unittest.mock import MagicMock, patch

import pytest

from linear.actions.create_issue_executor import CreateIssueExecutor
from linear.actions.create_sub_issue_executor import CreateSubIssueExecutor
from linear.actions.update_issue_executor import UpdateIssueExecutor
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

    async def test_partition_key(self, mock_linear_client: MagicMock) -> None:
        executor = create_executor(UpdateIssueExecutor, mock_linear_client)
        run = make_run("update_issue", {"issueId": "ENG-1", "title": "x"})
        assert await executor._get_partition_key(run) == "ENG-1"
        assert await executor._get_partition_key(make_run("update_issue", {})) is None
