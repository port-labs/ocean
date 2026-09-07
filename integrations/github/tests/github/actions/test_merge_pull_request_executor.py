from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.actions.merge_pull_request_executor import (
    MergePullRequestExecutor,
)
from github.actions.exceptions import MergePullRequestError
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)

MERGE_RESPONSE = {
    "sha": "abc123def456",
    "merged": True,
    "message": "Pull Request successfully merged",
}


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-1",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="merge_pull_request"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="merge_pull_request",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture(autouse=True)
def patched_ocean() -> Generator[MagicMock, None, None]:
    mock_client = MagicMock()
    mock_client.report_run_completed = AsyncMock()
    mock_client.post_run_log = AsyncMock()
    with patch("github.actions.merge_pull_request_executor.ocean") as mock_ocean:
        mock_ocean.port_client = mock_client
        yield mock_ocean


@pytest.fixture
def mock_port_client(patched_ocean: MagicMock) -> MagicMock:
    return patched_ocean.port_client


@pytest.fixture
def mock_rest_client() -> MagicMock:
    client = MagicMock(spec=GithubRestClient)
    client.base_url = "https://api.github.com"
    client.send_api_request = AsyncMock(return_value=MERGE_RESPONSE)
    client.get_rate_limit_status = MagicMock(return_value=None)
    return client


@pytest.fixture
def executor(
    mock_rest_client: MagicMock,
) -> Generator[MergePullRequestExecutor, None, None]:
    with patch(
        "github.actions.abstract_pull_request_executor.create_github_client_for_org",
        new=AsyncMock(return_value=mock_rest_client),
    ):
        yield MergePullRequestExecutor()


class TestMergePullRequestExecutor:
    @pytest.mark.asyncio
    async def test_happy_path_default_merge(
        self,
        executor: MergePullRequestExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
            }
        )
        await executor.execute(run)

        mock_rest_client.send_api_request.assert_called_once_with(
            "https://api.github.com/repos/port-labs/ocean/pulls/42/merge",
            method="PUT",
            json_data={"merge_method": "merge"},
            ignore_default_errors=False,
        )
        mock_port_client.report_run_completed.assert_called_once_with(
            run,
            success=True,
            message="Pull request #42 merged: https://github.com/port-labs/ocean/pull/42",
        )

    @pytest.mark.asyncio
    async def test_squash_merge_with_commit_title(
        self,
        executor: MergePullRequestExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
                "mergeMethod": "squash",
                "commitTitle": "feat: my feature",
                "commitMessage": "Full description",
            }
        )
        await executor.execute(run)

        mock_rest_client.send_api_request.assert_called_once_with(
            "https://api.github.com/repos/port-labs/ocean/pulls/42/merge",
            method="PUT",
            json_data={
                "merge_method": "squash",
                "commit_title": "feat: my feature",
                "commit_message": "Full description",
            },
            ignore_default_errors=False,
        )

    @pytest.mark.asyncio
    async def test_invalid_merge_method(
        self, executor: MergePullRequestExecutor
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
                "mergeMethod": "fast-forward",
            }
        )
        with pytest.raises(
            InvalidActionParametersException, match="mergeMethod must be one of"
        ):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_missing_required_inputs(
        self, executor: MergePullRequestExecutor
    ) -> None:
        for missing in ["org", "repo", "prNumber"]:
            props: dict[str, str] = {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
            }
            del props[missing]
            run = make_run(props)
            with pytest.raises(InvalidActionParametersException):
                await executor.execute(run)

    @pytest.mark.asyncio
    async def test_upstream_http_error_conflict(
        self,
        executor: MergePullRequestExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        response = httpx.Response(
            409,
            json={"message": "Head branch is out of date"},
            request=httpx.Request("PUT", "http://x"),
        )
        mock_rest_client.send_api_request = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "409", request=response.request, response=response
            )
        )
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
            }
        )
        with pytest.raises(MergePullRequestError, match="Head branch is out of date"):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_merge_not_successful(
        self,
        executor: MergePullRequestExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        mock_rest_client.send_api_request = AsyncMock(
            return_value={"sha": None, "merged": False, "message": "Not mergeable"}
        )
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
            }
        )
        with pytest.raises(MergePullRequestError, match="Not mergeable"):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_malformed_response(
        self,
        executor: MergePullRequestExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        mock_rest_client.send_api_request = AsyncMock(return_value={})
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
            }
        )
        with pytest.raises(MergePullRequestError, match="Failed to merge"):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_partition_key(self, executor: MergePullRequestExecutor) -> None:
        run = make_run({"org": "port-labs", "repo": "ocean", "prNumber": "42"})
        assert await executor._get_partition_key(run) == "port-labs/ocean"

    @pytest.mark.asyncio
    async def test_partition_key_missing_inputs_returns_none(
        self, executor: MergePullRequestExecutor
    ) -> None:
        assert await executor._get_partition_key(make_run({})) is None
