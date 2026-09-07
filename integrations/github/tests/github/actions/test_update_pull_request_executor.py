from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.actions.update_pull_request_executor import (
    UpdatePullRequestExecutor,
    UPDATING_STATUS_LABEL,
    UPDATED_STATUS_LABEL,
)
from github.actions.exceptions import UpdatePullRequestError
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
    "title": "Updated title",
}


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-1",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="update_pull_request"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="update_pull_request",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture(autouse=True)
def patched_ocean() -> Generator[MagicMock, None, None]:
    mock_client = MagicMock()
    mock_client.report_run_completed = AsyncMock()
    mock_client.post_run_log = AsyncMock()
    with patch("github.actions.update_pull_request_executor.ocean") as mock_ocean:
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
) -> Generator[UpdatePullRequestExecutor, None, None]:
    with patch(
        "github.actions.update_pull_request_executor.create_github_client_for_org",
        new=AsyncMock(return_value=mock_rest_client),
    ):
        yield UpdatePullRequestExecutor()


class TestUpdatePullRequestExecutor:
    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        executor: UpdatePullRequestExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
                "title": "Updated title",
                "body": "Updated body",
            }
        )
        await executor.execute(run)

        mock_rest_client.send_api_request.assert_called_once_with(
            "https://api.github.com/repos/port-labs/ocean/pulls/42",
            method="PATCH",
            json_data={"title": "Updated title", "body": "Updated body"},
            ignore_default_errors=False,
        )
        mock_port_client.report_run_completed.assert_called_once_with(
            run,
            success=True,
            message="Pull request #42 updated: https://github.com/port-labs/ocean/pull/42",
            status_label=UPDATED_STATUS_LABEL,
        )

    @pytest.mark.asyncio
    async def test_missing_required_inputs(
        self, executor: UpdatePullRequestExecutor
    ) -> None:
        for missing in ["org", "repo", "prNumber"]:
            props: dict[str, str] = {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
                "title": "t",
            }
            del props[missing]
            run = make_run(props)
            with pytest.raises(InvalidActionParametersException):
                await executor.execute(run)

    @pytest.mark.asyncio
    async def test_no_update_fields_raises(
        self, executor: UpdatePullRequestExecutor
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
            }
        )
        with pytest.raises(
            InvalidActionParametersException, match="At least one field"
        ):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_upstream_http_error(
        self,
        executor: UpdatePullRequestExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        response = httpx.Response(
            404,
            json={"message": "Not Found"},
            request=httpx.Request("PATCH", "http://x"),
        )
        mock_rest_client.send_api_request = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "404", request=response.request, response=response
            )
        )
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "999",
                "title": "t",
            }
        )
        with pytest.raises(UpdatePullRequestError, match="Not Found"):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_malformed_response(
        self,
        executor: UpdatePullRequestExecutor,
        mock_rest_client: MagicMock,
    ) -> None:
        mock_rest_client.send_api_request = AsyncMock(return_value={})
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "prNumber": "42",
                "title": "t",
            }
        )
        with pytest.raises(UpdatePullRequestError, match="empty or incomplete"):
            await executor.execute(run)

    @pytest.mark.asyncio
    async def test_partition_key(self, executor: UpdatePullRequestExecutor) -> None:
        run = make_run(
            {"org": "port-labs", "repo": "ocean", "prNumber": "42", "title": "t"}
        )
        assert await executor._get_partition_key(run) == "port-labs/ocean"

    @pytest.mark.asyncio
    async def test_partition_key_missing_inputs_returns_none(
        self, executor: UpdatePullRequestExecutor
    ) -> None:
        assert await executor._get_partition_key(make_run({})) is None
