from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response
from port_ocean.context.event import event_context
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from azure_devops.client.auth import PatAuthProvider
from azure_devops.client.azure_devops_client import API_PARAMS, AzureDevopsClient

MOCK_ORG_URL = "https://your_organization_url.com"
MOCK_AUTH_PROVIDER = PatAuthProvider("personal_access_token")
MOCK_AUTH_USERNAME = "port"


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "organization_url": MOCK_ORG_URL,
            "personal_access_token": "personal_access_token",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


async def async_mock_generator(items: list[Any]) -> AsyncGenerator[Any, None]:
    for item in items:
        yield item


def _pull_request(
    *,
    pull_request_id: int = 42,
    project_id: str = "proj-guid",
    repository_id: str = "repo-guid",
) -> dict[str, Any]:
    return {
        "pullRequestId": pull_request_id,
        "title": f"PR {pull_request_id}",
        "repository": {
            "id": repository_id,
            "project": {"id": project_id, "name": "Project One"},
        },
    }


@pytest.mark.asyncio
class TestPullRequestClientMethods:
    @pytest.fixture
    def client(self) -> AzureDevopsClient:
        return AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, MOCK_AUTH_USERNAME)

    async def test_get_pull_request_commits_paginates_with_continuation_token(
        self, client: AzureDevopsClient
    ) -> None:
        page_one = [{"commitId": "newest", "author": {"date": "2026-09-09T18:00:00Z"}}]
        page_two = [{"commitId": "oldest", "author": {"date": "2026-09-08T10:00:00Z"}}]

        with patch.object(
            client,
            "_get_paginated_by_top_and_continuation_token",
            return_value=async_mock_generator([page_one, page_two]),
        ) as mock_paginated:
            result = await client.get_pull_request_commits(
                "proj-guid", "repo-guid", "42"
            )

        assert [commit["commitId"] for commit in result] == ["newest", "oldest"]
        mock_paginated.assert_called_once_with(
            f"{MOCK_ORG_URL}/proj-guid/_apis/git/repositories/repo-guid/pullRequests/42/commits",
            additional_params=API_PARAMS,
        )

    async def test_get_pull_request_commits_404_returns_empty_list(
        self, client: AzureDevopsClient
    ) -> None:
        with patch.object(client, "send_request", AsyncMock(return_value=None)):
            result = await client.get_pull_request_commits(
                "proj-guid", "repo-guid", "42"
            )

        assert result == []

    async def test_get_pull_request_threads_returns_value(
        self, client: AzureDevopsClient
    ) -> None:
        threads = [
            {
                "id": 1,
                "publishedDate": "2026-09-09T18:03:03.070Z",
                "properties": {
                    "CodeReviewThreadType": {"$value": "VoteUpdate"},
                },
                "comments": [
                    {
                        "author": {"id": "reviewer-1"},
                        "publishedDate": "2026-09-09T18:03:03.070Z",
                    }
                ],
            }
        ]

        with patch.object(
            client,
            "send_request",
            AsyncMock(
                return_value=Response(
                    status_code=200, json={"value": threads, "count": 1}
                )
            ),
        ) as mock_send:
            result = await client.get_pull_request_threads(
                "proj-guid", "repo-guid", "42"
            )

        assert result == threads
        mock_send.assert_called_once_with(
            "GET",
            f"{MOCK_ORG_URL}/proj-guid/_apis/git/repositories/repo-guid/pullRequests/42/threads",
            params=API_PARAMS,
        )

    async def test_get_pull_request_threads_404_returns_empty_list(
        self, client: AzureDevopsClient
    ) -> None:
        with patch.object(client, "send_request", AsyncMock(return_value=None)):
            result = await client.get_pull_request_threads(
                "proj-guid", "repo-guid", "42"
            )

        assert result == []


@pytest.mark.asyncio
class TestEnrichPullRequests:
    @pytest.fixture
    def client(self) -> AzureDevopsClient:
        return AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, MOCK_AUTH_USERNAME)

    async def test_flags_off_makes_no_api_calls_and_attaches_no_fields(
        self, client: AzureDevopsClient
    ) -> None:
        batch = [_pull_request()]

        with (
            patch.object(
                client, "get_pull_request_commits", AsyncMock()
            ) as mock_commits,
            patch.object(
                client, "get_pull_request_threads", AsyncMock()
            ) as mock_threads,
        ):
            result = await client.enrich_pull_requests(batch)

        assert result == batch
        assert "__commits" not in result[0]
        assert "__threads" not in result[0]
        mock_commits.assert_not_called()
        mock_threads.assert_not_called()

    async def test_commits_flag_attaches_raw_commits(
        self, client: AzureDevopsClient
    ) -> None:
        batch = [_pull_request()]
        later = {"commitId": "later", "author": {"date": "2026-09-09T18:25:11Z"}}
        earlier = {"commitId": "earlier", "author": {"date": "2026-09-08T10:00:00Z"}}

        with (
            patch.object(
                client,
                "get_pull_request_commits",
                AsyncMock(return_value=[later, earlier]),
            ) as mock_commits,
            patch.object(
                client, "get_pull_request_threads", AsyncMock()
            ) as mock_threads,
        ):
            result = await client.enrich_pull_requests(batch, enrich_with_commits=True)

        assert result[0]["__commits"] == [later, earlier]
        assert "__threads" not in result[0]
        mock_commits.assert_called_once_with("proj-guid", "repo-guid", "42")
        mock_threads.assert_not_called()

    async def test_review_discussion_flag_attaches_raw_threads(
        self, client: AzureDevopsClient
    ) -> None:
        batch = [_pull_request()]
        threads = [
            {
                "id": 1,
                "properties": {"CodeReviewThreadType": {"$value": "VoteUpdate"}},
                "comments": [
                    {
                        "author": {"id": "reviewer-1"},
                        "publishedDate": "2026-09-09T18:49:31.754Z",
                    }
                ],
            }
        ]

        with (
            patch.object(
                client, "get_pull_request_commits", AsyncMock()
            ) as mock_commits,
            patch.object(
                client, "get_pull_request_threads", AsyncMock(return_value=threads)
            ) as mock_threads,
        ):
            result = await client.enrich_pull_requests(
                batch, enrich_with_review_discussion=True
            )

        assert result[0]["__threads"] == threads
        mock_threads.assert_called_once_with("proj-guid", "repo-guid", "42")
        mock_commits.assert_not_called()

    async def test_both_flags_fetch_concurrently_and_attach_raw_payloads(
        self, client: AzureDevopsClient
    ) -> None:
        batch = [_pull_request()]
        commits = [{"commitId": "sha", "author": {"date": "2026-09-09T18:25:11Z"}}]
        threads = [
            {
                "id": 1,
                "properties": {"CodeReviewThreadType": {"$value": "VoteUpdate"}},
            }
        ]

        with (
            patch.object(
                client, "get_pull_request_commits", AsyncMock(return_value=commits)
            ),
            patch.object(
                client, "get_pull_request_threads", AsyncMock(return_value=threads)
            ),
        ):
            result = await client.enrich_pull_requests(
                batch,
                enrich_with_commits=True,
                enrich_with_review_discussion=True,
            )

        assert result[0]["__commits"] == commits
        assert result[0]["__threads"] == threads

    async def test_single_pr_fetch_failure_does_not_abort_batch(
        self, client: AzureDevopsClient
    ) -> None:
        failing = _pull_request(pull_request_id=1)
        succeeding = _pull_request(pull_request_id=2)
        commits = [{"commitId": "sha", "author": {"date": "2026-09-09T18:25:11Z"}}]

        async def commits_side_effect(
            project_id: str, repository_id: str, pull_request_id: str
        ) -> list[dict[str, Any]]:
            if pull_request_id == "1":
                raise RuntimeError("rate limited")
            return commits

        with patch.object(
            client, "get_pull_request_commits", side_effect=commits_side_effect
        ):
            result = await client.enrich_pull_requests(
                [failing, succeeding], enrich_with_commits=True
            )

        assert result[0]["__commits"] is None
        assert result[1]["__commits"] == commits

    async def test_threads_failure_does_not_drop_commits(
        self, client: AzureDevopsClient
    ) -> None:
        batch = [_pull_request()]
        commits = [{"commitId": "sha", "author": {"date": "2026-09-09T18:25:11Z"}}]

        with (
            patch.object(
                client, "get_pull_request_commits", AsyncMock(return_value=commits)
            ),
            patch.object(
                client,
                "get_pull_request_threads",
                AsyncMock(side_effect=RuntimeError("forbidden")),
            ),
        ):
            result = await client.enrich_pull_requests(
                batch,
                enrich_with_commits=True,
                enrich_with_review_discussion=True,
            )

        assert result[0]["__commits"] == commits
        assert result[0]["__threads"] is None

    async def test_missing_ids_skip_without_api_calls(
        self, client: AzureDevopsClient
    ) -> None:
        batch = [{"title": "broken"}]

        with (
            patch.object(
                client, "get_pull_request_commits", AsyncMock()
            ) as mock_commits,
            patch.object(
                client, "get_pull_request_threads", AsyncMock()
            ) as mock_threads,
        ):
            result = await client.enrich_pull_requests(batch, enrich_with_commits=True)

        assert "__commits" not in result[0]
        mock_commits.assert_not_called()
        mock_threads.assert_not_called()

    async def test_generate_pull_requests_enriches_when_flags_enabled(
        self, client: AzureDevopsClient
    ) -> None:
        pull_requests = [_pull_request()]
        enriched = [{**pull_requests[0], "__commits": [{"commitId": "sha"}]}]

        async def mock_generate_repositories(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {
                    "id": "repo-guid",
                    "name": "Repository One",
                    "project": {"id": "proj-guid", "name": "Project One"},
                }
            ]

        async def mock_paginate(
            url: str,
            additional_params: dict[str, Any] | None = None,
            max_results: int | None = None,
            **kwargs: Any,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield pull_requests

        async with event_context("test_event"):
            with (
                patch.object(
                    client,
                    "generate_repositories",
                    side_effect=mock_generate_repositories,
                ),
                patch.object(
                    client,
                    "_get_paginated_by_top_and_skip",
                    side_effect=mock_paginate,
                ),
                patch.object(
                    client,
                    "enrich_pull_requests",
                    AsyncMock(return_value=enriched),
                ) as mock_enrich,
            ):
                batches: list[dict[str, Any]] = []
                async for batch in client.generate_pull_requests(
                    enrich_with_commits=True
                ):
                    batches.extend(batch)

        assert batches == enriched
        mock_enrich.assert_called_once_with(
            pull_requests,
            enrich_with_commits=True,
            enrich_with_review_discussion=False,
        )

    async def test_generate_pull_requests_skips_enrichment_when_flags_off(
        self, client: AzureDevopsClient
    ) -> None:
        pull_requests = [_pull_request()]

        async def mock_generate_repositories(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {
                    "id": "repo-guid",
                    "name": "Repository One",
                    "project": {"id": "proj-guid", "name": "Project One"},
                }
            ]

        async def mock_paginate(
            url: str,
            additional_params: dict[str, Any] | None = None,
            max_results: int | None = None,
            **kwargs: Any,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield pull_requests

        async with event_context("test_event"):
            with (
                patch.object(
                    client,
                    "generate_repositories",
                    side_effect=mock_generate_repositories,
                ),
                patch.object(
                    client,
                    "_get_paginated_by_top_and_skip",
                    side_effect=mock_paginate,
                ),
                patch.object(
                    client, "enrich_pull_requests", AsyncMock()
                ) as mock_enrich,
            ):
                batches: list[dict[str, Any]] = []
                async for batch in client.generate_pull_requests():
                    batches.extend(batch)

        assert batches == pull_requests
        mock_enrich.assert_not_called()

    async def test_get_pull_request_skips_enrichment_when_flags_off(
        self, client: AzureDevopsClient
    ) -> None:
        pull_request = _pull_request()

        with (
            patch.object(
                client,
                "send_request",
                AsyncMock(return_value=Response(status_code=200, json=pull_request)),
            ),
            patch.object(client, "enrich_pull_requests", AsyncMock()) as mock_enrich,
        ):
            result = await client.get_pull_request("42")

        assert result == pull_request
        mock_enrich.assert_not_called()

    async def test_get_pull_request_enriches_when_flags_enabled(
        self, client: AzureDevopsClient
    ) -> None:
        pull_request = _pull_request()
        enriched = {**pull_request, "__commits": [{"commitId": "sha"}]}

        with (
            patch.object(
                client,
                "send_request",
                AsyncMock(return_value=Response(status_code=200, json=pull_request)),
            ),
            patch.object(
                client,
                "enrich_pull_requests",
                AsyncMock(return_value=[enriched]),
            ) as mock_enrich,
        ):
            result = await client.get_pull_request(
                "42",
                enrich_with_commits=True,
                enrich_with_review_discussion=True,
            )

        assert result == enriched
        mock_enrich.assert_called_once_with(
            [pull_request],
            enrich_with_commits=True,
            enrich_with_review_discussion=True,
            concurrency=1,
        )
