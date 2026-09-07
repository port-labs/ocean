from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.actions.review_pull_request_executor import (
    ReviewPullRequestExecutor,
)
from github.actions.exceptions import ReviewPullRequestError
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)

REVIEW_RESPONSE = {
    "id": 999,
    "state": "APPROVED",
    "html_url": "https://github.com/port-labs/ocean/pull/42#pullrequestreview-999",
}


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-1",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="review_pull_request"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="review_pull_request",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture(autouse=True)
def patched_ocean() -> Generator[MagicMock, None, None]:
    mock_client = MagicMock()
    mock_client.report_run_completed = AsyncMock()
    mock_client.post_run_log = AsyncMock()
    with patch("github.actions.review_pull_request_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_client
        yield mock_ocean


@pytest.fixture
def mock_port_client(patched_ocean: MagicMock) -> MagicMock:
    return patched_ocean.port_client


@pytest.fixture
def mock_rest_client() -> MagicMock:
    client = MagicMock(spec=GithubRestClient)
    client.base_url = "https://api.github.com"
    client.send_api_request = AsyncMock(return_value=REVIEW_RESPONSE)
    client.get_rate_limit_status = MagicMock(return_value=None)
    return client


@pytest.fixture
def executor(
    mock_rest_client: MagicMock,
) -> Generator[ReviewPullRequestExecutor, None, None]:
    with patch(
        "github.actions.abstract_pull_request_executor.create_github_client_for_org",
        new=AsyncMock(return_value=mock_rest_client),
    ):
        yield ReviewPullRequestExecutor()


class TestReviewPullRequestExecutor:
    @pytest.mark.asyncio
    async def test_approve(
        self,
        executor: ReviewPullRequestExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
                "event": "APPROVE",
            }
        )
        await executor.execute(run)

        mock_rest_client.send_api_request.assert_called_once_with(
            "https://api.github.com/repos/port-labs/ocean/pulls/42/reviews",
            method="POST",
            json_data={"event": "APPROVE"},
            ignore_default_errors=False,
        )
        mock_port_client.report_run_completed.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_changes_with_body(
        self,
        executor: ReviewPullRequestExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
                "event": "REQUEST_CHANGES",
                "body": "Please fix the tests",
            }
        )
        await executor.execute(run)

        mock_rest_client.send_api_request.assert_called_once_with(
            "https://api.github.com/repos/port-labs/ocean/pulls/42/reviews",
            method="POST",
            json_data={"event": "REQUEST_CHANGES", "body": "Please fix the tests"},
            ignore_default_errors=False,
        )

    @pytest.mark.asyncio
    async def test_request_changes_without_body_raises(
        self, executor: ReviewPullRequestExecutor
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
                "event": "REQUEST_CHANGES",
            }
        )
        with pytest.raises(InvalidActionParametersException, match="body is required"):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_invalid_event(self, executor: ReviewPullRequestExecutor) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
                "event": "REJECT",
            }
        )
        with pytest.raises(
            InvalidActionParametersException, match="event must be one of"
        ):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_missing_required_inputs(
        self, executor: ReviewPullRequestExecutor
    ) -> None:
        for missing in ["org", "repo", "prNumber", "event"]:
            props: dict[str, str] = {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
                "event": "APPROVE",
            }
            del props[missing]
            run = make_run(props)
            with pytest.raises(InvalidActionParametersException):
                await executor.execute(run)

    @pytest.mark.asyncio
    async def test_upstream_http_error(
        self,
        executor: ReviewPullRequestExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        response = httpx.Response(
            422,
            json={"message": "Validation Failed"},
            request=httpx.Request("POST", "http://x"),
        )
        mock_rest_client.send_api_request = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "422", request=response.request, response=response
            )
        )
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
                "event": "APPROVE",
            }
        )
        with pytest.raises(ReviewPullRequestError, match="Validation Failed"):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_malformed_response(
        self,
        executor: ReviewPullRequestExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        mock_rest_client.send_api_request = AsyncMock(return_value={})
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
                "event": "APPROVE",
            }
        )
        with pytest.raises(ReviewPullRequestError, match="empty or incomplete"):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_partition_key(self, executor: ReviewPullRequestExecutor) -> None:
        run = make_run(
            {"org": "port-labs", "repo": "ocean", "prNumber": "42", "event": "APPROVE"}
        )
        assert await executor._get_partition_key(run) == "port-labs/ocean"
