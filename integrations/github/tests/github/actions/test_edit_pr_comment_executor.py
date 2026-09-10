from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.actions.edit_pr_comment_executor import EditPrCommentExecutor
from github.actions.exceptions import PullRequestCommentError
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.core.models import ActionRun
from tests.github.actions.conftest import make_action_run

COMMENT_RESPONSE = {
    "id": 555,
    "body": "Updated comment",
    "html_url": "https://github.com/port-labs/ocean/pull/42#issuecomment-555",
}


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return make_action_run("edit_pr_comment", execution_properties)


@pytest.fixture(autouse=True)
def patched_ocean() -> Generator[MagicMock, None, None]:
    mock_client = MagicMock()
    mock_client.post_run_log = AsyncMock()
    mock_client.report_run_completed = AsyncMock()
    with patch("github.actions.edit_pr_comment_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_client
        yield mock_ocean


@pytest.fixture
def executor(
    mock_rest_client: MagicMock,
) -> Generator[EditPrCommentExecutor, None, None]:
    with patch(
        "github.actions.abstract_github_executor.create_github_client_for_org",
        new=AsyncMock(return_value=mock_rest_client),
    ):
        yield EditPrCommentExecutor()


class TestEditPrCommentExecutor:
    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        executor: EditPrCommentExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "commentId": "555",
                "body": "Updated comment",
            }
        )

        mock_rest_client.send_api_request.return_value = COMMENT_RESPONSE

        await executor.execute(run)

        mock_rest_client.send_api_request.assert_awaited_once_with(
            "https://api.github.com/repos/port-labs/ocean/issues/comments/555",
            method="PATCH",
            json_data={"body": "Updated comment"},
            ignore_default_errors=False,
        )

        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message="Comment updated: https://github.com/port-labs/ocean/pull/42#issuecomment-555",
        )

    @pytest.mark.asyncio
    async def test_missing_required_inputs(
        self,
        executor: EditPrCommentExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run({"org": "port-labs", "repo": "ocean"})

        with pytest.raises(
            InvalidActionParametersException,
            match="org, repo, commentId, and body are required",
        ):
            await executor.execute(run)

        mock_rest_client.send_api_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upstream_http_error(
        self,
        executor: EditPrCommentExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "commentId": "555",
                "body": "Updated comment",
            }
        )

        request = httpx.Request(
            "PATCH",
            "https://api.github.com/repos/port-labs/ocean/issues/comments/555",
        )
        response = httpx.Response(404, json={"message": "Not Found"}, request=request)
        mock_rest_client.send_api_request.side_effect = httpx.HTTPStatusError(
            "404", request=request, response=response
        )

        with pytest.raises(PullRequestCommentError, match="Could not edit comment"):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_malformed_response(
        self,
        executor: EditPrCommentExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "commentId": "555",
                "body": "Updated comment",
            }
        )

        mock_rest_client.send_api_request.return_value = {}

        with pytest.raises(PullRequestCommentError, match="empty or incomplete"):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_partition_key(
        self,
        executor: EditPrCommentExecutor,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "commentId": "555",
                "body": "Updated comment",
            }
        )
        assert await executor._get_partition_key(run) is None

    @pytest.mark.asyncio
    async def test_partition_key_missing_inputs_returns_none(
        self,
        executor: EditPrCommentExecutor,
    ) -> None:
        run = make_run({"org": "port-labs"})
        assert await executor._get_partition_key(run) is None
