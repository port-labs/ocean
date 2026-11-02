from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from gitlab.clients.gitlab_client import GitLabClient, _ancestor_dirs
from gitlab.helpers.utils import build_search_query

pytestmark = pytest.mark.asyncio

SINCE = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)
PROJECT: dict[str, Any] = {
    "id": 1,
    "path_with_namespace": "group/repo",
    "default_branch": "main",
}


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


@pytest.fixture
def client() -> GitLabClient:
    return GitLabClient("https://gitlab.example.com", "test-token")


async def _gen(items: list[Any]) -> AsyncGenerator[Any, None]:
    for item in items:
        yield item


async def _collect(stream: Any) -> list[Any]:
    return [item async for item in stream]


def _commits(client: GitLabClient, commits: list[list[dict[str, Any]]]) -> None:
    client.rest = MagicMock()
    client.rest.get_paginated_project_resource = MagicMock(
        side_effect=lambda *args, **kwargs: _gen(commits)
    )


async def test_changed_paths_returns_new_paths_only(client: GitLabClient) -> None:
    _commits(client, [[{"id": "base", "parent_ids": ["p1"]}]])
    client.compare_repository = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "diffs": [
                {"new_path": "a.yaml", "deleted_file": False},
                {"new_path": "gone.yaml", "deleted_file": True},
            ]
        }
    )

    result = await client.get_changed_paths_since(PROJECT, SINCE, "main")

    assert result == ["a.yaml"]
    client.compare_repository.assert_awaited_once_with("group/repo", "base", "main")


async def test_changed_paths_none_without_base_commit(client: GitLabClient) -> None:
    _commits(client, [])
    client.compare_repository = AsyncMock()  # type: ignore[method-assign]

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") is None
    client.compare_repository.assert_not_awaited()


async def test_changed_paths_none_for_root_commit(client: GitLabClient) -> None:
    _commits(client, [[{"id": "root", "parent_ids": []}]])
    client.compare_repository = AsyncMock()  # type: ignore[method-assign]

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") is None
    client.compare_repository.assert_not_awaited()


async def test_changed_paths_none_on_compare_timeout(client: GitLabClient) -> None:
    _commits(client, [[{"id": "base", "parent_ids": ["p1"]}]])
    client.compare_repository = AsyncMock(  # type: ignore[method-assign]
        return_value={"diffs": [], "compare_timeout": True}
    )

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") is None


async def test_changed_paths_none_on_http_error(client: GitLabClient) -> None:
    _commits(client, [[{"id": "base", "parent_ids": ["p1"]}]])
    client.compare_repository = AsyncMock(  # type: ignore[method-assign]
        side_effect=httpx.ConnectError("boom")
    )

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") is None


@pytest.mark.parametrize(
    "path, expected",
    [
        ("c.txt", set()),
        ("a/c.txt", {"a"}),
        ("a/b/c.txt", {"a", "a/b"}),
    ],
)
def test_ancestor_dirs(path: str, expected: set[str]) -> None:
    assert _ancestor_dirs(path) == expected


async def test_changed_files_fall_back_to_tree_walk(client: GitLabClient) -> None:
    query = build_search_query("**/*.yaml")
    client.get_changed_paths_since = AsyncMock(return_value=None)  # type: ignore[method-assign]
    full_walk_batch = [{"path": "full/a.yaml", "project_id": 1}]

    with patch.object(
        client,
        "_search_files_in_repository",
        side_effect=lambda *args, **kwargs: _gen([full_walk_batch]),
    ) as search:
        batches = await _collect(
            client._search_changed_files_in_project(PROJECT, query, SINCE)
        )

    assert batches == [full_walk_batch]
    assert search.call_args.kwargs["should_use_tree"] is True


async def test_changed_files_filtered_by_pattern(client: GitLabClient) -> None:
    query = build_search_query("**/*.yaml")
    client.get_changed_paths_since = AsyncMock(  # type: ignore[method-assign]
        return_value=["a/b/app.yaml", "README.md"]
    )
    client._process_file_batch = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda batch, repo, skip_parsing: batch
    )

    batches = await _collect(
        client._search_changed_files_in_project(PROJECT, query, SINCE)
    )

    assert [[file["path"] for file in batch] for batch in batches] == [["a/b/app.yaml"]]
    assert batches[0][0]["ref"] == "main"
    assert batches[0][0]["project_id"] == 1


async def test_changed_folders_yield_only_changed_children(
    client: GitLabClient,
) -> None:
    client.get_project = AsyncMock(return_value=PROJECT)  # type: ignore[method-assign]
    client.get_changed_paths_since = AsyncMock(  # type: ignore[method-assign]
        return_value=["docs/api/v1/openapi.yaml", "docs/readme.md", "other/x.txt"]
    )
    tree_items = [
        {"type": "tree", "path": "docs/api"},
        {"type": "tree", "path": "docs/unchanged"},
        {"type": "blob", "path": "docs/readme.md"},
    ]
    client.get_repository_tree = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda *args, **kwargs: _gen([tree_items])
    )

    batches = await _collect(
        client.get_repository_folders_since("docs", "group/repo", SINCE)
    )

    assert batches == [
        [
            {
                "folder": {"type": "tree", "path": "docs/api"},
                "repo": PROJECT,
                "__branch": "main",
            }
        ]
    ]
    assert client.get_repository_tree.call_args.args[1] == "docs"


async def test_changed_folders_fall_back_to_full_listing(
    client: GitLabClient,
) -> None:
    client.get_project = AsyncMock(return_value=PROJECT)  # type: ignore[method-assign]
    client.get_changed_paths_since = AsyncMock(return_value=None)  # type: ignore[method-assign]

    with patch.object(
        client,
        "get_repository_folders",
        side_effect=lambda *args, **kwargs: _gen([[{"folder": {"path": "docs"}}]]),
    ) as full_listing:
        batches = await _collect(
            client.get_repository_folders_since("docs", "group/repo", SINCE)
        )

    assert batches == [[{"folder": {"path": "docs"}}]]
    full_listing.assert_called_once_with("docs", "group/repo", "main")
