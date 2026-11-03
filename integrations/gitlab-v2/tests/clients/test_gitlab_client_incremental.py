from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.context.ocean import initialize_port_ocean_context, ocean
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from gitlab.clients.gitlab_client import GitLabClient, _ancestor_dirs
from gitlab.clients.rest_client import RestClient
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


def _push(
    created_at: str, commit_from: str | None, ref: str = "main"
) -> dict[str, Any]:
    return {
        "created_at": created_at,
        "push_data": {"ref": ref, "ref_type": "branch", "commit_from": commit_from},
    }


def _mock_rest(
    client: GitLabClient,
    events: list[dict[str, Any]],
    commits: dict[str, dict[str, Any]],
    tip_committed_date: str | None = "2026-10-01T00:00:00+00:00",
) -> None:
    client.rest = MagicMock()

    async def send_api_request(
        method: str, path: str, params: dict[str, Any] | None = None, **_: Any
    ) -> Any:
        if path.endswith("/events"):
            assert params is not None
            size, page = params["per_page"], params["page"]
            return events[(page - 1) * size : page * size]
        sha = path.rsplit("/", 1)[-1]
        if sha == "main":
            return {"committed_date": tip_committed_date}
        return commits[sha]

    client.rest.send_api_request = AsyncMock(side_effect=send_api_request)


async def test_changed_paths_compares_from_branch_tip_before_first_push(
    client: GitLabClient,
) -> None:
    _mock_rest(
        client,
        [_push("2026-10-18T10:00:00Z", "C0"), _push("2026-10-18T11:00:00Z", "C1")],
        {"C0": {"id": "C0", "parent_ids": ["P"]}},
    )
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
    client.compare_repository.assert_awaited_once_with("group/repo", "C0", "main")


async def test_late_pushed_commit_is_not_skipped(client: GitLabClient) -> None:
    """A commit made before the cursor but pushed after it must be compared.

    C was committed before the cursor, so a commit-time lookup would pick C as the base
    and drop C's own changes. The push event says the branch tip was C0 before the push,
    so the compare starts there and includes C.
    """
    _mock_rest(
        client,
        [_push("2026-10-18T10:00:00Z", "C0")],
        {"C0": {"id": "C0", "parent_ids": ["P"]}},
    )
    client.compare_repository = AsyncMock(  # type: ignore[method-assign]
        return_value={"diffs": [{"new_path": "late.yaml", "deleted_file": False}]}
    )

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") == ["late.yaml"]
    assert client.compare_repository.call_args.args[1] == "C0"


async def test_pushes_to_other_refs_are_ignored(client: GitLabClient) -> None:
    _mock_rest(client, [_push("2026-10-18T10:00:00Z", "C0", ref="feature")], {})
    client.compare_repository = AsyncMock()  # type: ignore[method-assign]

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") == []
    client.compare_repository.assert_not_awaited()


async def test_pushes_are_read_across_pages_until_cursor(client: GitLabClient) -> None:
    """Events are newest first; paging stops at the first event at or before the cursor."""
    _mock_rest(
        client,
        [
            _push("2026-10-18T12:00:00Z", "C2"),
            _push("2026-10-18T11:00:00Z", "C1"),
            _push("2026-10-18T08:00:00Z", "C0"),
        ],
        {"C1": {"id": "C1", "parent_ids": ["C0"]}},
    )
    client.compare_repository = AsyncMock(  # type: ignore[method-assign]
        return_value={"diffs": [{"new_path": "a.yaml", "deleted_file": False}]}
    )

    with patch.object(RestClient, "DEFAULT_PAGE_SIZE", 2):
        assert await client.get_changed_paths_since(PROJECT, SINCE, "main") == [
            "a.yaml"
        ]

    client.compare_repository.assert_awaited_once_with("group/repo", "C1", "main")
    event_calls = [
        call.kwargs["params"]
        for call in client.rest.send_api_request.call_args_list  # type: ignore[attr-defined]
        if call.args[1].endswith("/events")
    ]
    assert [params["page"] for params in event_calls] == [1, 2]
    assert all(params["action"] == "pushed" for params in event_calls)


async def test_unreadable_push_events_need_full_listing(client: GitLabClient) -> None:
    """A GET 403/404 on the events comes back as {}; that must not read as "no pushes"."""
    client.rest = MagicMock()
    client.rest.send_api_request = AsyncMock(return_value={})
    client.compare_repository = AsyncMock()  # type: ignore[method-assign]

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") is None
    client.compare_repository.assert_not_awaited()


async def test_no_cursor_event_within_page_cap_needs_full_listing(
    client: GitLabClient,
) -> None:
    events = [_push(f"2026-10-20T0{hour}:00:00Z", f"C{hour}") for hour in range(1, 6)]
    _mock_rest(client, events, {})
    client.compare_repository = AsyncMock()  # type: ignore[method-assign]

    with (
        patch.object(RestClient, "DEFAULT_PAGE_SIZE", 2),
        patch("gitlab.clients.gitlab_client.PUSH_EVENT_MAX_PAGES", 2),
    ):
        assert await client.get_changed_paths_since(PROJECT, SINCE, "main") is None

    client.compare_repository.assert_not_awaited()


@pytest.fixture
def run_cache() -> Iterator[dict[str, Any]]:
    """An in-memory cache provider, so the per-run cache behaves as it does during a sync."""
    store: dict[str, Any] = {}

    async def get(key: str) -> Any:
        return store.get(key)

    async def set_(key: str, value: Any) -> None:
        store[key] = value

    cache = MagicMock()
    cache.get = AsyncMock(side_effect=get)
    cache.set = AsyncMock(side_effect=set_)
    with patch.object(ocean.app, "cache_provider", cache):
        yield store


@pytest.mark.usefixtures("run_cache")
async def test_compare_is_computed_once_per_run(client: GitLabClient) -> None:
    _mock_rest(
        client,
        [_push("2026-10-18T10:00:00Z", "C0")],
        {"C0": {"id": "C0", "parent_ids": ["P"]}},
    )
    client.compare_repository = AsyncMock(  # type: ignore[method-assign]
        return_value={"diffs": [{"new_path": "a.yaml", "deleted_file": False}]}
    )

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") == ["a.yaml"]
    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") == ["a.yaml"]
    client.compare_repository.assert_awaited_once()


@pytest.mark.usefixtures("run_cache")
async def test_unchanged_result_is_cached_for_the_run(client: GitLabClient) -> None:
    _mock_rest(client, [], {}, tip_committed_date="2026-10-01T00:00:00+00:00")
    client.compare_repository = AsyncMock()  # type: ignore[method-assign]

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") == []
    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") == []
    # One events page and one tip read, both made by the first call only.
    assert client.rest.send_api_request.await_count == 2  # type: ignore[attr-defined]
    client.compare_repository.assert_not_awaited()


async def test_no_push_and_tip_before_cursor_is_unchanged(
    client: GitLabClient,
) -> None:
    _mock_rest(client, [], {}, tip_committed_date="2026-10-01T00:00:00+00:00")
    client.compare_repository = AsyncMock()  # type: ignore[method-assign]

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") == []
    client.compare_repository.assert_not_awaited()


async def test_no_push_but_tip_after_cursor_needs_full_listing(
    client: GitLabClient,
) -> None:
    _mock_rest(client, [], {}, tip_committed_date="2026-10-20T00:00:00+00:00")
    client.compare_repository = AsyncMock()  # type: ignore[method-assign]

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") is None
    client.compare_repository.assert_not_awaited()


async def test_branch_created_after_cursor_needs_full_listing(
    client: GitLabClient,
) -> None:
    _mock_rest(client, [_push("2026-10-18T10:00:00Z", None)], {})
    client.compare_repository = AsyncMock()  # type: ignore[method-assign]

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") is None
    client.compare_repository.assert_not_awaited()


async def test_changed_paths_none_for_root_base_commit(client: GitLabClient) -> None:
    _mock_rest(
        client,
        [_push("2026-10-18T10:00:00Z", "C0")],
        {"C0": {"id": "C0", "parent_ids": []}},
    )
    client.compare_repository = AsyncMock()  # type: ignore[method-assign]

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") is None
    client.compare_repository.assert_not_awaited()


async def test_changed_paths_none_on_compare_timeout(client: GitLabClient) -> None:
    _mock_rest(
        client,
        [_push("2026-10-18T10:00:00Z", "C0")],
        {"C0": {"id": "C0", "parent_ids": ["P"]}},
    )
    client.compare_repository = AsyncMock(  # type: ignore[method-assign]
        return_value={"diffs": [], "compare_timeout": True}
    )

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") is None


async def test_compare_without_diffs_needs_full_listing(client: GitLabClient) -> None:
    """A 403/404 compare comes back as {} and must not read as "nothing changed"."""
    _mock_rest(
        client,
        [_push("2026-10-18T10:00:00Z", "C0")],
        {"C0": {"id": "C0", "parent_ids": ["P"]}},
    )
    client.compare_repository = AsyncMock(return_value={})  # type: ignore[method-assign]

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") is None


async def test_unreadable_base_commit_needs_full_listing(client: GitLabClient) -> None:
    _mock_rest(client, [_push("2026-10-18T10:00:00Z", "C0")], {"C0": {}})
    client.compare_repository = AsyncMock()  # type: ignore[method-assign]

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") is None
    client.compare_repository.assert_not_awaited()


async def test_unreadable_branch_tip_needs_full_listing(client: GitLabClient) -> None:
    _mock_rest(client, [], {}, tip_committed_date=None)
    client.compare_repository = AsyncMock()  # type: ignore[method-assign]

    assert await client.get_changed_paths_since(PROJECT, SINCE, "main") is None
    client.compare_repository.assert_not_awaited()


async def test_changed_paths_none_on_http_error(client: GitLabClient) -> None:
    _mock_rest(
        client,
        [_push("2026-10-18T10:00:00Z", "C0")],
        {"C0": {"id": "C0", "parent_ids": ["P"]}},
    )
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


async def test_unreadable_project_yields_no_folders(client: GitLabClient) -> None:
    """An explicit branch skips the project's default branch, so an empty project must stop here."""
    client.get_project = AsyncMock(return_value={})  # type: ignore[method-assign]
    client.get_changed_paths_since = AsyncMock()  # type: ignore[method-assign]

    batches = await _collect(
        client.get_repository_folders_since("docs", "group/repo", SINCE, branch="dev")
    )

    assert batches == []
    client.get_changed_paths_since.assert_not_awaited()


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
