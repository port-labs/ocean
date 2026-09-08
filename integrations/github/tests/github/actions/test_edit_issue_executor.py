"""Tests for EditIssueExecutor."""

from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.actions.edit_issue_executor import EditIssueExecutor
from github.actions.exceptions import IssueActionError
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)

ACTION = "edit_issue"

ISSUE_RESPONSE = {
    "number": 7,
    "id": 123456,
    "title": "Updated issue",
    "html_url": "https://github.com/port-labs/ocean/issues/7",
    "state": "open",
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
    pc = MagicMock()
    pc.post_run_log = AsyncMock()
    pc.report_run_completed = AsyncMock()
    return pc


@pytest.fixture
def executor(
    mock_rest_client: MagicMock,
) -> Generator[EditIssueExecutor, None, None]:
    with patch(
        "github.actions.abstract_github_executor.create_github_client_for_org",
        new=AsyncMock(return_value=mock_rest_client),
    ):
        yield EditIssueExecutor()


class TestEditIssueExecutor:
    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        executor: EditIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "issueNumber": 7,
                "title": "Updated issue",
            }
        )

        with patch("github.actions.edit_issue_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_rest_client.send_api_request.assert_awaited_once()
        call_kwargs = mock_rest_client.send_api_request.call_args
        assert "repos/port-labs/ocean/issues/7" in call_kwargs.args[0]
        assert call_kwargs.kwargs["method"] == "PATCH"
        assert call_kwargs.kwargs["json_data"] == {"title": "Updated issue"}

        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message="Issue #7 updated: https://github.com/port-labs/ocean/issues/7",
        )

    @pytest.mark.asyncio
    async def test_no_update_fields_raises(
        self,
        executor: EditIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run({"org": "port-labs", "repo": "ocean", "issueNumber": 7})

        with pytest.raises(
            InvalidActionParametersException, match="At least one field"
        ):
            with patch("github.actions.edit_issue_executor.ocean") as mock_ocean:
                mock_ocean.port_client = mock_port_client
                await executor.execute(run)

        mock_rest_client.send_api_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_org_raises(
        self,
        executor: EditIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run({"repo": "ocean", "issueNumber": 7, "title": "Updated issue"})

        with pytest.raises(
            InvalidActionParametersException, match="org.*repo.*issueNumber"
        ):
            with patch("github.actions.edit_issue_executor.ocean") as mock_ocean:
                mock_ocean.port_client = mock_port_client
                await executor.execute(run)

        mock_rest_client.send_api_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_repo_raises(
        self,
        executor: EditIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run({"org": "port-labs", "issueNumber": 7, "title": "Updated issue"})

        with pytest.raises(
            InvalidActionParametersException, match="org.*repo.*issueNumber"
        ):
            with patch("github.actions.edit_issue_executor.ocean") as mock_ocean:
                mock_ocean.port_client = mock_port_client
                await executor.execute(run)

        mock_rest_client.send_api_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_issue_number_raises(
        self,
        executor: EditIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run({"org": "port-labs", "repo": "ocean", "title": "Updated issue"})

        with pytest.raises(
            InvalidActionParametersException, match="org.*repo.*issueNumber"
        ):
            with patch("github.actions.edit_issue_executor.ocean") as mock_ocean:
                mock_ocean.port_client = mock_port_client
                await executor.execute(run)

        mock_rest_client.send_api_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_http_error_raises(
        self,
        executor: EditIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "issueNumber": 7,
                "title": "Updated issue",
            }
        )

        request = httpx.Request(
            "PATCH", "https://api.github.com/repos/port-labs/ocean/issues/7"
        )
        response = httpx.Response(404, json={"message": "Not Found"}, request=request)
        mock_rest_client.send_api_request.side_effect = httpx.HTTPStatusError(
            "404", request=request, response=response
        )

        with pytest.raises(IssueActionError, match="Not Found"):
            with patch("github.actions.edit_issue_executor.ocean") as mock_ocean:
                mock_ocean.port_client = mock_port_client
                await executor.execute(run)

    @pytest.mark.asyncio
    async def test_malformed_response_raises(
        self,
        executor: EditIssueExecutor,
        mock_rest_client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "issueNumber": 7,
                "title": "Updated issue",
            }
        )
        mock_rest_client.send_api_request.return_value = {}

        with pytest.raises(IssueActionError, match="empty or incomplete"):
            with patch("github.actions.edit_issue_executor.ocean") as mock_ocean:
                mock_ocean.port_client = mock_port_client
                await executor.execute(run)

    @pytest.mark.asyncio
    async def test_partition_key(self, executor: EditIssueExecutor) -> None:
        run = make_run({"org": "port-labs", "repo": "ocean", "issueNumber": 7})
        assert await executor._get_partition_key(run) == "port-labs/ocean"

    @pytest.mark.asyncio
    async def test_partition_key_missing(self, executor: EditIssueExecutor) -> None:
        run = make_run({"issueNumber": 7})
        assert await executor._get_partition_key(run) is None

    def test_action_name(self, executor: EditIssueExecutor) -> None:
        assert executor.ACTION_NAME == ACTION
