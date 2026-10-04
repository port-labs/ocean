from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.actions.close_issue_executor import CloseIssueExecutor
from github.actions.exceptions import CloseIssueError
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)

ACTION = "close_issue"

ISSUE_RESPONSE = {
    "number": 7,
    "id": 123456,
    "title": "Test issue",
    "html_url": "https://github.com/port-labs/ocean/issues/7",
    "state": "closed",
}


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-123",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier=ACTION),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType=ACTION,
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def mock_rest_client() -> MagicMock:
    client = MagicMock(spec=GithubRestClient)
    client.base_url = "https://api.github.com"
    client.send_api_request = AsyncMock(return_value=ISSUE_RESPONSE)
    client.get_rate_limit_status = MagicMock(return_value=None)
    return client


@pytest.fixture
def mock_port_client() -> MagicMock:
    port_client = MagicMock()
    port_client.post_run_log = AsyncMock()
    port_client.report_run_completed = AsyncMock()
    return port_client


@pytest.fixture
def executor(
    mock_rest_client: MagicMock,
) -> Generator[CloseIssueExecutor, None, None]:
    with patch(
        "github.actions.abstract_github_executor.create_github_client_for_org",
        new=AsyncMock(return_value=mock_rest_client),
    ):
        yield CloseIssueExecutor()


class TestCloseIssueExecutor:
    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        executor: CloseIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "issueNumber": 7,
                "stateReason": "completed",
            }
        )

        with patch("github.actions.close_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_rest_client.send_api_request.assert_awaited_once()
        call_kwargs = mock_rest_client.send_api_request.call_args
        assert "repos/port-labs/ocean/issues/7" in call_kwargs.args[0]
        assert call_kwargs.kwargs["method"] == "PATCH"
        assert call_kwargs.kwargs["json_data"] == {
            "state": "closed",
            "state_reason": "completed",
        }

        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message="Issue #7 closed: https://github.com/port-labs/ocean/issues/7",
            status_label="Issue closed",
        )

    @pytest.mark.asyncio
    async def test_defaults_to_completed(
        self,
        executor: CloseIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "issueNumber": 7,
            }
        )

        with patch("github.actions.close_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        call_kwargs = mock_rest_client.send_api_request.call_args
        assert call_kwargs.kwargs["json_data"] == {
            "state": "closed",
            "state_reason": "completed",
        }

    @pytest.mark.asyncio
    async def test_with_not_planned(
        self,
        executor: CloseIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "issueNumber": 7,
                "stateReason": "not_planned",
            }
        )

        with patch("github.actions.close_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        call_kwargs = mock_rest_client.send_api_request.call_args
        assert call_kwargs.kwargs["json_data"] == {
            "state": "closed",
            "state_reason": "not_planned",
        }

    @pytest.mark.asyncio
    async def test_invalid_state_reason_raises(
        self,
        executor: CloseIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "issueNumber": 7,
                "stateReason": "invalid",
            }
        )

        with pytest.raises(InvalidActionParametersException):
            with patch("github.actions.close_issue_executor.ocean") as mock_ocean:
                mock_ocean.port_client = mock_port_client
                await executor.execute(run)

        mock_rest_client.send_api_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_required_inputs(self, executor: CloseIssueExecutor) -> None:
        for missing in ["org", "repo", "issueNumber"]:
            props: dict[str, Any] = {
                "org": "port-labs",
                "repo": "ocean",
                "issueNumber": 7,
            }
            del props[missing]
            run = make_run(props)
            with pytest.raises(InvalidActionParametersException):
                with patch("github.actions.close_issue_executor.ocean"):
                    await executor.execute(run)

    @pytest.mark.asyncio
    async def test_http_error_raises(
        self,
        executor: CloseIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "issueNumber": 7,
                "stateReason": "completed",
            }
        )

        request = httpx.Request(
            "PATCH", "https://api.github.com/repos/port-labs/ocean/issues/7"
        )
        response = httpx.Response(404, json={"message": "Not Found"}, request=request)
        mock_rest_client.send_api_request.side_effect = httpx.HTTPStatusError(
            "404", request=request, response=response
        )

        with pytest.raises(CloseIssueError, match="Not Found"):
            with patch("github.actions.close_issue_executor.ocean") as mock_ocean:
                mock_ocean.port_client = mock_port_client
                await executor.execute(run)

    @pytest.mark.asyncio
    async def test_incomplete_response(
        self,
        executor: CloseIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "issueNumber": 7,
                "stateReason": "completed",
            }
        )
        mock_rest_client.send_api_request.return_value = {}

        with pytest.raises(CloseIssueError, match="incomplete response"):
            with patch("github.actions.close_issue_executor.ocean") as mock_ocean:
                mock_ocean.port_client = mock_port_client
                await executor.execute(run)

    @pytest.mark.asyncio
    async def test_partition_key(self, executor: CloseIssueExecutor) -> None:
        run = make_run({"org": "port-labs", "repo": "ocean", "issueNumber": 7})
        assert await executor._get_partition_key(run) == "port-labs/ocean"

    @pytest.mark.asyncio
    async def test_partition_key_missing(self, executor: CloseIssueExecutor) -> None:
        run = make_run({"issueNumber": 7})
        assert await executor._get_partition_key(run) is None

    @pytest.mark.asyncio
    async def test_duplicate_with_issue_id(
        self,
        executor: CloseIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "issueNumber": 7,
                "stateReason": "duplicate",
                "duplicateIssueId": 42,
            }
        )

        with patch("github.actions.close_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        call_kwargs = mock_rest_client.send_api_request.call_args
        assert call_kwargs.kwargs["json_data"] == {
            "state": "closed",
            "state_reason": "duplicate",
            "duplicate_issue_id": 42,
        }

    @pytest.mark.asyncio
    async def test_duplicate_without_issue_id_raises(
        self,
        executor: CloseIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "issueNumber": 7,
                "stateReason": "duplicate",
            }
        )

        with pytest.raises(
            InvalidActionParametersException, match="duplicateIssueId is required"
        ):
            with patch("github.actions.close_issue_executor.ocean") as mock_ocean:
                mock_ocean.port_client = mock_port_client
                await executor.execute(run)

        mock_rest_client.send_api_request.assert_not_awaited()

    def test_action_name(self, executor: CloseIssueExecutor) -> None:
        assert executor.ACTION_NAME == ACTION
