"""Tests for Linear status, comment, and document action executors (batch 2)."""

from unittest.mock import MagicMock, patch

import pytest

from linear.actions.add_comment_executor import AddCommentExecutor
from linear.actions.add_document_executor import AddDocumentExecutor
from linear.actions.change_status_executor import ChangeStatusExecutor
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
        mock_issue_mutations.update_issue.assert_awaited_once_with(
            "ENG-1", {"stateId": "state-1"}
        )


@pytest.mark.asyncio
class TestAddCommentExecutor:
    async def test_happy_path(
        self,
        mock_port_client: MagicMock,
        mock_linear_client: MagicMock,
        mock_comment_mutations: MagicMock,
    ) -> None:
        executor = create_executor(AddCommentExecutor, mock_linear_client)
        run = make_run(
            "add_comment",
            {"issueId": "ENG-1", "body": "Looks good"},
        )
        with (
            patch("linear.actions.add_comment_executor.ocean") as mock_ocean,
            patch(
                "linear.actions.add_comment_executor.CommentMutations",
                return_value=mock_comment_mutations,
            ),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_comment_mutations.create_comment.assert_awaited_once_with(
            "ENG-1", "Looks good"
        )


@pytest.mark.asyncio
class TestAddDocumentExecutor:
    async def test_requires_issue_or_project(
        self, mock_port_client: MagicMock, mock_linear_client: MagicMock
    ) -> None:
        executor = create_executor(AddDocumentExecutor, mock_linear_client)
        run = make_run("add_document", {"title": "Notes"})
        with patch("linear.actions.add_document_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError):
                await executor.execute(run)
