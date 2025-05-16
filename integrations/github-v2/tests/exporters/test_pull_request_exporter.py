from typing import Any, AsyncGenerator
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from github.core.exporters.pull_request_exporter import PullRequestExporter
from github.clients.base_client import AbstractGithubClient
from integration import GithubPullRequestSelector
from github.utils import PullRequestState
from port_ocean.context.event import event_context
from github.core.options import SinglePullRequestOptions, ListPullRequestOptions

TEST_PULL_REQUESTS = [
    {
        "id": 1,
        "number": 101,
        "title": "Fix bug in login",
        "state": "open",
        "html_url": "https://github.com/test-org/repo1/pull/101",
    },
    {
        "id": 2,
        "number": 102,
        "title": "Add new feature",
        "state": "open",
        "html_url": "https://github.com/test-org/repo1/pull/102",
    },
]

TEST_REPOS = [
    {"id": 1, "name": "repo1", "full_name": "test-org/repo1"},
    {"id": 2, "name": "repo2", "full_name": "test-org/repo2"},
]


@pytest.mark.asyncio
class TestPullRequestExporter:

    async def test_get_resource_with_explicit_params(
        self, client: AbstractGithubClient
    ) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_PULL_REQUESTS[0]
        mock_response.text = ""

        exporter = PullRequestExporter(client)

        with patch.object(
            client, "send_api_request", AsyncMock(return_value=mock_response)
        ) as mock_request:
            # Test with options containing repo_name and pr_number
            pr = await exporter.get_resource(
                SinglePullRequestOptions(repo_name="repo1", pr_number=101)
            )

            assert pr == TEST_PULL_REQUESTS[0]

            mock_request.assert_called_once_with(
                f"repos/{client.organization}/repo1/pulls/101"
            )

    async def test_get_resource_error(self, client: AbstractGithubClient) -> None:
        # Create a mock error response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Not Found"

        exporter = PullRequestExporter(client)

        with patch.object(
            client, "send_api_request", AsyncMock(return_value=mock_response)
        ) as mock_request:
            with pytest.raises(ValueError):
                await exporter.get_resource(
                    SinglePullRequestOptions(repo_name="repo1", pr_number=999)
                )

            mock_request.assert_called_once_with(
                f"repos/{client.organization}/repo1/pulls/999"
            )

    async def test_get_paginated_resources(self, client: AbstractGithubClient) -> None:
        selector = GithubPullRequestSelector(query="true", state=PullRequestState.OPEN)
        exporter = PullRequestExporter(client)

        # Create async mocks for the nested requests
        async def mock_repos_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_REPOS

        async def mock_prs_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_PULL_REQUESTS

        with patch.object(client, "send_paginated_request") as mock_paginated:
            # Configure the mock to return different responses based on the endpoint
            mock_paginated.side_effect = lambda endpoint, *args, **kwargs: (
                mock_repos_request()
                if "repos" in endpoint and "pulls" not in endpoint
                else mock_prs_request()
            )

            async with event_context("test_event"):
                # Convert selector to options dict
                options = ListPullRequestOptions(
                    state=selector.state, repo_name="repo1"
                )
                prs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(prs) == 1
                assert len(prs[0]) == 2
                assert prs[0] == TEST_PULL_REQUESTS

            mock_paginated.assert_called_once_with(
                "repos/test-org/repo1/pulls", {"state": "open"}
            )
