from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.actions.delete_pr_comment_executor import DeletePrCommentExecutor
from github.actions.exceptions import PullRequestCommentError
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-123",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="delete_pr_comment"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="delete_pr_comment",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture(autouse=True)
def patched_ocean() -> Generator[MagicMock, None, None]:
    mock_client = MagicMock()
    mock_client.post_run_log = AsyncMock()
    mock_client.report_run_completed = AsyncMock()
    with patch("github.actions.delete_pr_comment_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_client
        yield mock_ocean


@pytest.fixture
def mock_port_client(patched_ocean: MagicMock) -> MagicMock:
    return patched_ocean.port_client


@pytest.fixture
def mock_rest_client() -> MagicMock:
    client = MagicMock(spec=GithubRestClient)
    client.base_url = "https://api.github.com"
    client.send_api_request = AsyncMock()
    client.make_request = AsyncMock()
    client.get_rate_limit_status = MagicMock(return_value=None)
    return client


@pytest.fixture
def executor(
    mock_rest_client: MagicMock,
) -> Generator[DeletePrCommentExecutor, None, None]:
    with patch(
        "github.actions.abstract_github_executor.create_github_client_for_org",
        new=AsyncMock(return_value=mock_rest_client),
    ):
        yield DeletePrCommentExecutor()


class TestDeletePrCommentExecutor:
    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        executor: DeletePrCommentExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "commentId": 555,
            }
        )

        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_rest_client.make_request.return_value = mock_response

        await executor.execute(run)

        mock_rest_client.make_request.assert_awaited_once_with(
            "https://api.github.com/repos/port-labs/ocean/issues/comments/555",
            method="DELETE",
            ignore_default_errors=False,
        )

        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message="Comment 555 deleted from port-labs/ocean",
        )

    @pytest.mark.asyncio
    async def test_missing_required_inputs(
        self,
        executor: DeletePrCommentExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run({"org": "port-labs", "repo": "ocean"})

        with pytest.raises(
            InvalidActionParametersException,
            match="org, repo, and commentId are required",
        ):
            await executor.execute(run)

        mock_rest_client.make_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upstream_http_error(
        self,
        executor: DeletePrCommentExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "commentId": 555,
            }
        )

        request = httpx.Request(
            "DELETE",
            "https://api.github.com/repos/port-labs/ocean/issues/comments/555",
        )
        response = httpx.Response(404, json={"message": "Not Found"}, request=request)
        mock_rest_client.make_request.side_effect = httpx.HTTPStatusError(
            "404", request=request, response=response
        )

        with pytest.raises(PullRequestCommentError, match="Could not delete comment"):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_unexpected_status_code(
        self,
        executor: DeletePrCommentExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "commentId": 555,
            }
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_rest_client.make_request.return_value = mock_response

        with pytest.raises(PullRequestCommentError, match="unexpected status code 200"):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_partition_key(
        self,
        executor: DeletePrCommentExecutor,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "commentId": 555,
            }
        )
        assert await executor._get_partition_key(run) is None

    @pytest.mark.asyncio
    async def test_partition_key_missing_inputs_returns_none(
        self,
        executor: DeletePrCommentExecutor,
    ) -> None:
        run = make_run({"org": "port-labs"})
        assert await executor._get_partition_key(run) is None
