from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from gitlab.clients.gitlab_client import GitLabClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "gitlab_host": "https://gitlab.example.com",
            "gitlab_token": "test-token",
        }
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


async def async_mock_generator(items: list[Any]) -> AsyncGenerator[Any, None]:
    for item in items:
        yield item


def _merge_request(
    *,
    mr_id: int = 1,
    iid: int = 2,
    project_id: int = 123,
    author_id: int = 22245283,
) -> dict[str, Any]:
    return {
        "id": mr_id,
        "iid": iid,
        "project_id": project_id,
        "title": f"MR {iid}",
        "author": {"id": author_id, "username": "author"},
    }


@pytest.mark.asyncio
class TestMergeRequestClientMethods:
    @pytest.fixture
    def client(self) -> GitLabClient:
        return GitLabClient("https://gitlab.example.com", "test-token")

    async def test_get_merge_request_commits_paginates_fully(
        self, client: GitLabClient
    ) -> None:
        page_one = [{"id": "newest", "created_at": "2026-09-09T18:00:00.000+00:00"}]
        page_two = [{"id": "oldest", "created_at": "2026-09-08T10:00:00.000+00:00"}]

        with patch.object(
            client.rest,
            "get_paginated_project_resource",
            return_value=async_mock_generator([page_one, page_two]),
        ) as mock_paginated:
            result = await client.get_merge_request_commits(123, 2)

        assert [commit["id"] for commit in result] == ["newest", "oldest"]
        mock_paginated.assert_called_once_with("123", "merge_requests/2/commits")

    async def test_get_merge_request_notes_paginates_fully(
        self, client: GitLabClient
    ) -> None:
        page_one = [{"id": i, "body": "assigned to @x"} for i in range(100)]
        page_two = [
            {
                "id": 101,
                "body": "approved this merge request",
                "system": True,
                "created_at": "2026-09-09T18:49:31.754Z",
                "author": {"id": 1001},
            }
        ]

        with patch.object(
            client.rest,
            "get_paginated_project_resource",
            return_value=async_mock_generator([page_one, page_two]),
        ) as mock_paginated:
            result = await client.get_merge_request_notes(123, 2)

        assert len(result) == 101
        assert result[-1]["body"] == "approved this merge request"
        mock_paginated.assert_called_once_with(
            "123",
            "merge_requests/2/notes",
            params={"sort": "asc", "order_by": "created_at"},
        )

    async def test_get_merge_request_notes_pagination_via_send_api_request(
        self, client: GitLabClient
    ) -> None:
        page_one = [{"id": i} for i in range(100)]
        page_two = [{"id": 100}, {"id": 101}]

        async def fake_send(
            method: str,
            path: str,
            params: dict[str, Any] | None = None,
            data: dict[str, Any] | None = None,
        ) -> list[dict[str, Any]]:
            page = (params or {}).get("page", 1)
            if page == 1:
                return page_one
            if page == 2:
                return page_two
            return []

        with patch.object(client.rest, "send_api_request", side_effect=fake_send):
            result = await client.get_merge_request_notes(123, 2)

        assert [note["id"] for note in result] == list(range(100)) + [100, 101]


@pytest.mark.asyncio
class TestEnrichMergeRequests:
    @pytest.fixture
    def client(self) -> GitLabClient:
        return GitLabClient("https://gitlab.example.com", "test-token")

    async def test_flags_off_makes_no_api_calls_and_attaches_no_fields(
        self, client: GitLabClient
    ) -> None:
        batch = [_merge_request()]

        with (
            patch.object(
                client, "get_merge_request_commits", AsyncMock()
            ) as mock_commits,
            patch.object(client, "get_merge_request_notes", AsyncMock()) as mock_notes,
        ):
            result = await client.enrich_merge_requests(batch)

        assert result == batch
        assert "__commits" not in result[0]
        assert "__notes" not in result[0]
        mock_commits.assert_not_called()
        mock_notes.assert_not_called()

    async def test_commits_flag_attaches_raw_commits(
        self, client: GitLabClient
    ) -> None:
        batch = [_merge_request()]
        later = {
            "id": "later",
            "created_at": "2026-09-09T18:25:11.000+00:00",
        }
        earlier = {
            "id": "earlier",
            "created_at": "2026-09-08T10:00:00.000+00:00",
        }

        with (
            patch.object(
                client,
                "get_merge_request_commits",
                AsyncMock(return_value=[later, earlier]),
            ) as mock_commits,
            patch.object(client, "get_merge_request_notes", AsyncMock()) as mock_notes,
        ):
            result = await client.enrich_merge_requests(batch, enrich_with_commits=True)

        assert result[0]["__commits"] == [later, earlier]
        assert "__notes" not in result[0]
        mock_commits.assert_called_once_with(123, 2)
        mock_notes.assert_not_called()

    async def test_review_discussion_flag_attaches_raw_notes(
        self, client: GitLabClient
    ) -> None:
        batch = [_merge_request()]
        notes = [
            {
                "body": "requested changes",
                "created_at": "2026-09-09T18:03:03.070Z",
                "system": True,
                "author": {"id": 1001},
            },
            {
                "body": "approved this merge request",
                "created_at": "2026-09-09T18:49:31.754Z",
                "system": True,
                "author": {"id": 1001},
            },
        ]

        with (
            patch.object(
                client, "get_merge_request_commits", AsyncMock()
            ) as mock_commits,
            patch.object(
                client, "get_merge_request_notes", AsyncMock(return_value=notes)
            ) as mock_notes,
        ):
            result = await client.enrich_merge_requests(
                batch, enrich_with_review_discussion=True
            )

        assert result[0]["__notes"] == notes
        mock_notes.assert_called_once_with(123, 2)
        mock_commits.assert_not_called()

    async def test_both_flags_fetch_concurrently_and_attach_raw_payloads(
        self, client: GitLabClient
    ) -> None:
        batch = [_merge_request()]
        commits = [{"id": "sha", "created_at": "2026-09-09T18:25:11.000+00:00"}]
        notes = [
            {
                "body": "approved this merge request",
                "created_at": "2026-09-09T18:49:31.754Z",
                "system": True,
                "author": {"id": 1001},
            }
        ]

        with (
            patch.object(
                client, "get_merge_request_commits", AsyncMock(return_value=commits)
            ),
            patch.object(
                client, "get_merge_request_notes", AsyncMock(return_value=notes)
            ),
        ):
            result = await client.enrich_merge_requests(
                batch,
                enrich_with_commits=True,
                enrich_with_review_discussion=True,
            )

        assert result[0]["__commits"] == commits
        assert result[0]["__notes"] == notes

    async def test_single_mr_fetch_failure_does_not_abort_batch(
        self, client: GitLabClient
    ) -> None:
        failing = _merge_request(mr_id=1, iid=1)
        succeeding = _merge_request(mr_id=2, iid=2)
        commits = [{"id": "sha", "created_at": "2026-09-09T18:25:11.000+00:00"}]

        async def commits_side_effect(
            project_id: int, iid: int
        ) -> list[dict[str, Any]]:
            if iid == 1:
                raise RuntimeError("rate limited")
            return commits

        with patch.object(
            client, "get_merge_request_commits", side_effect=commits_side_effect
        ):
            result = await client.enrich_merge_requests(
                [failing, succeeding], enrich_with_commits=True
            )

        assert result[0]["__commits"] is None
        assert result[1]["__commits"] == commits

    async def test_notes_failure_does_not_drop_commits(
        self, client: GitLabClient
    ) -> None:
        batch = [_merge_request()]
        commits = [{"id": "sha", "created_at": "2026-09-09T18:25:11.000+00:00"}]

        with (
            patch.object(
                client, "get_merge_request_commits", AsyncMock(return_value=commits)
            ),
            patch.object(
                client,
                "get_merge_request_notes",
                AsyncMock(side_effect=RuntimeError("forbidden")),
            ),
        ):
            result = await client.enrich_merge_requests(
                batch,
                enrich_with_commits=True,
                enrich_with_review_discussion=True,
            )

        assert result[0]["__commits"] == commits
        assert result[0]["__notes"] is None

    async def test_missing_project_or_iid_skips_without_api_calls(
        self, client: GitLabClient
    ) -> None:
        batch = [{"id": 9, "title": "broken"}]

        with (
            patch.object(
                client, "get_merge_request_commits", AsyncMock()
            ) as mock_commits,
            patch.object(client, "get_merge_request_notes", AsyncMock()) as mock_notes,
        ):
            result = await client.enrich_merge_requests(batch, enrich_with_commits=True)

        assert "__commits" not in result[0]
        mock_commits.assert_not_called()
        mock_notes.assert_not_called()
