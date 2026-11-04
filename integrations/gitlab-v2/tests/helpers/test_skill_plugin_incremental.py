from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, AsyncGenerator, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from gitlab.clients.gitlab_client import GitLabClient
from gitlab.helpers.utils import ChangedPaths
from gitlab.helpers import skill_plugin_resync as resync

pytestmark = pytest.mark.asyncio

SINCE = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)
PROJECT: dict[str, Any] = {
    "id": 1,
    "path_with_namespace": "group/repo",
    "default_branch": "main",
}
SKILL_GLOBS = ["skills/**/SKILL.md"]


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


def _selector(
    globs: list[str] | None = None, include_skill_folder: bool = False
) -> Any:
    return SimpleNamespace(
        paths=[SimpleNamespace(path=glob, repos=[]) for glob in globs or SKILL_GLOBS],
        include_skill_folder=include_skill_folder,
    )


async def test_plugin_changed_when_compare_unavailable(client: GitLabClient) -> None:
    client.changed_paths_since = AsyncMock(return_value=ChangedPaths(paths=None))  # type: ignore[method-assign]

    assert await resync._plugin_changed(client, PROJECT, SINCE, ["claude"]) is True


async def test_plugin_changed_on_manifest_change(client: GitLabClient) -> None:
    client.changed_paths_since = AsyncMock(  # type: ignore[method-assign]
        return_value=ChangedPaths(paths=["README.md", ".claude-plugin/plugin.json"])
    )

    assert await resync._plugin_changed(client, PROJECT, SINCE, ["claude"]) is True


async def test_plugin_unchanged_for_unrelated_paths(client: GitLabClient) -> None:
    client.changed_paths_since = AsyncMock(  # type: ignore[method-assign]
        return_value=ChangedPaths(paths=["src/app.py"])
    )

    assert await resync._plugin_changed(client, PROJECT, SINCE, ["claude"]) is False


async def test_plugin_incremental_rebuilds_only_touched_projects(
    client: GitLabClient,
) -> None:
    touched = {
        "id": 1,
        "path_with_namespace": "group/touched",
        "default_branch": "main",
    }
    untouched = {
        "id": 2,
        "path_with_namespace": "group/quiet",
        "default_branch": "main",
    }
    client.changed_paths_since = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda project_path, *_: ChangedPaths(
            paths=(
                [".claude-plugin/plugin.json"]
                if project_path == touched["path_with_namespace"]
                else ["src/app.py"]
            )
        )
    )
    rebuilt = [{"plugin": {"name": "p"}, "repo": touched, "__branch": "main"}]

    with (
        patch.object(
            resync,
            "_iter_projects",
            side_effect=lambda *a, **k: _gen([[touched, untouched]]),
        ),
        patch.object(
            resync, "_plugins_for_projects", AsyncMock(return_value=rebuilt)
        ) as rebuild,
    ):
        batches = await _collect(
            resync.resync_plugins_incremental(
                client,
                cast(Any, SimpleNamespace(providers=["claude"], repos=[])),
                None,
                SINCE,
            )
        )

    assert batches == [rebuilt]
    assert rebuild.call_args.args[1] == [touched]


async def test_skill_incremental_fetches_only_changed_skill_md(
    client: GitLabClient,
) -> None:
    client.changed_paths_since = AsyncMock(  # type: ignore[method-assign]
        return_value=ChangedPaths(paths=["skills/foo/SKILL.md", "README.md"])
    )
    client._process_file_batch = AsyncMock(return_value=[])  # type: ignore[method-assign]

    with patch.object(
        resync, "_iter_projects", side_effect=lambda *a, **k: _gen([[PROJECT]])
    ):
        await _collect(
            resync.resync_skills_incremental(client, _selector(), None, SINCE)
        )

    files = client._process_file_batch.call_args.args[0]
    assert files == [{"path": "skills/foo/SKILL.md", "ref": "main", "project_id": 1}]


async def test_skill_incremental_skips_unrelated_changes(client: GitLabClient) -> None:
    client.changed_paths_since = AsyncMock(  # type: ignore[method-assign]
        return_value=ChangedPaths(paths=["README.md"])
    )
    client._process_file_batch = AsyncMock(return_value=[])  # type: ignore[method-assign]

    with patch.object(
        resync, "_iter_projects", side_effect=lambda *a, **k: _gen([[PROJECT]])
    ):
        await _collect(
            resync.resync_skills_incremental(client, _selector(), None, SINCE)
        )

    client._process_file_batch.assert_not_awaited()


async def test_skill_incremental_falls_back_to_full_search_per_project(
    client: GitLabClient,
) -> None:
    client.changed_paths_since = AsyncMock(return_value=ChangedPaths(paths=None))  # type: ignore[method-assign]
    client.search_files_matching_patterns = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda *a, **k: _gen([])
    )

    with patch.object(
        resync, "_iter_projects", side_effect=lambda *a, **k: _gen([[PROJECT]])
    ):
        await _collect(
            resync.resync_skills_incremental(client, _selector(), None, SINCE)
        )

    assert client.search_files_matching_patterns.call_args.kwargs["repositories"] == [
        PROJECT
    ]


async def test_skill_incremental_adds_owner_for_bundle_file(
    client: GitLabClient,
) -> None:
    client.changed_paths_since = AsyncMock(  # type: ignore[method-assign]
        return_value=ChangedPaths(paths=["skills/foo/scripts/run.py"])
    )
    client._process_file_batch = AsyncMock(return_value=[])  # type: ignore[method-assign]

    with (
        patch.object(
            resync, "_iter_projects", side_effect=lambda *a, **k: _gen([[PROJECT]])
        ),
        patch.object(
            resync,
            "find_owning_skill_md_paths",
            AsyncMock(return_value={"skills/foo/SKILL.md"}),
        ),
    ):
        await _collect(
            resync.resync_skills_incremental(
                client, _selector(include_skill_folder=True), None, SINCE
            )
        )

    files = client._process_file_batch.call_args.args[0]
    assert [file["path"] for file in files] == ["skills/foo/SKILL.md"]


async def test_bundle_file_ignored_without_include_skill_folder(
    client: GitLabClient,
) -> None:
    client.changed_paths_since = AsyncMock(  # type: ignore[method-assign]
        return_value=ChangedPaths(paths=["skills/foo/scripts/run.py"])
    )
    client._process_file_batch = AsyncMock(return_value=[])  # type: ignore[method-assign]

    with patch.object(
        resync, "_iter_projects", side_effect=lambda *a, **k: _gen([[PROJECT]])
    ):
        await _collect(
            resync.resync_skills_incremental(client, _selector(), None, SINCE)
        )

    client._process_file_batch.assert_not_awaited()
