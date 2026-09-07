from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.actions.create_pull_request_executor import (
    CreatePullRequestExecutor,
    CREATING_STATUS_LABEL,
    CREATED_STATUS_LABEL,
)
from github.actions.exceptions import CreatePullRequestError
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)

PR_RESPONSE = {
    "number": 42,
    "id": 123456,
    "html_url": "https://github.com/port-labs/ocean/pull/42",
    "state": "open",
    "title": "Add feature",
    "body": "Description",
    "draft": False,
}


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-1",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="create_pull_request"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="create_pull_request",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture(autouse=True)
def patched_ocean() -> Generator[MagicMock, None, None]:
    mock_client = MagicMock()
    mock_client.report_run_completed = AsyncMock()
    mock_client.post_run_log = AsyncMock()
    with patch("github.actions.create_pull_request_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_client
        yield mock_ocean


@pytest.fixture
def mock_port_client(patched_ocean: MagicMock) -> MagicMock:
    return patched_ocean.port_client


@pytest.fixture
def mock_rest_client() -> MagicMock:
    client = MagicMock(spec=GithubRestClient)
    client.base_url = "https://api.github.com"
    client.send_api_request = AsyncMock(return_value=PR_RESPONSE)
    client.get_rate_limit_status = MagicMock(return_value=None)
    return client


@pytest.fixture
def executor(
    mock_rest_client: MagicMock,
) -> Generator[CreatePullRequestExecutor, None, None]:
    with patch(
        "github.actions.create_pull_request_executor.create_github_client_for_org",
        new=AsyncMock(return_value=mock_rest_client),
    ):
        yield CreatePullRequestExecutor()


class TestCreatePullRequestExecutor:
    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        executor: CreatePullRequestExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "title": "Add feature",
                "head": "feature-branch",
                "base": "main",
                "body": "Description",
                "draft": False,
            }
        )
        await executor.execute(run)

        mock_rest_client.send_api_request.assert_called_once_with(
            "https://api.github.com/repos/port-labs/ocean/pulls",
            method="POST",
            json_data={
                "title": "Add feature",
                "head": "feature-branch",
                "base": "main",
                "body": "Description",
                "draft": False,
            },
            ignore_default_errors=False,
        )
        mock_port_client.report_run_completed.assert_called_once_with(
            run,
            success=True,
            message="Pull request #42 created: https://github.com/port-labs/ocean/pull/42",
            status_label=CREATED_STATUS_LABEL,
        )
        assert (
            mock_port_client.post_run_log.call_args.kwargs["status_label"]
            == CREATING_STATUS_LABEL
        )

    @pytest.mark.asyncio
    async def test_happy_path_minimal_inputs(
        self,
        executor: CreatePullRequestExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "title": "Add feature",
                "head": "feature-branch",
                "base": "main",
            }
        )
        await executor.execute(run)

        mock_rest_client.send_api_request.assert_called_once_with(
            "https://api.github.com/repos/port-labs/ocean/pulls",
            method="POST",
            json_data={
                "title": "Add feature",
                "head": "feature-branch",
                "base": "main",
            },
            ignore_default_errors=False,
        )

    @pytest.mark.asyncio
    async def test_missing_required_inputs(
        self, executor: CreatePullRequestExecutor
    ) -> None:
        for missing in ["org", "repo", "title", "head", "base"]:
            props = {
                "org": "port-labs",
                "repo": "ocean",
                "title": "Add feature",
                "head": "feature-branch",
                "base": "main",
            }
            del props[missing]
            run = make_run(props)
            with pytest.raises(InvalidActionParametersException):
                await executor.execute(run)

    @pytest.mark.asyncio
    async def test_upstream_http_error(
        self,
        executor: CreatePullRequestExecutor,
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
                "title": "Add feature",
                "head": "feature-branch",
                "base": "main",
            }
        )
        with pytest.raises(CreatePullRequestError, match="Validation Failed"):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_malformed_response(
        self,
        executor: CreatePullRequestExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        mock_rest_client.send_api_request = AsyncMock(return_value={})
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "title": "Add feature",
                "head": "feature-branch",
                "base": "main",
            }
        )
        with pytest.raises(CreatePullRequestError, match="empty or incomplete"):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_partition_key(self, executor: CreatePullRequestExecutor) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "title": "t",
                "head": "h",
                "base": "b",
            }
        )
        assert await executor._get_partition_key(run) == "port-labs/ocean"

    @pytest.mark.asyncio
    async def test_partition_key_missing_inputs_returns_none(
        self, executor: CreatePullRequestExecutor
    ) -> None:
        assert await executor._get_partition_key(make_run({})) is None
        assert await executor._get_partition_key(make_run({"org": "x"})) is None
