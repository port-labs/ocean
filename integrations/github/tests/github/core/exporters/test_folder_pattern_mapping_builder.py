import importlib
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from github.core.exporters.folder_exporter.utils import FolderPatternMappingBuilder
from integration import (
    FolderSelector,
    RepositoryBranchMapping,
    RepositorySourceModel,
)
from port_ocean.context.event import event_context
from port_ocean.core.incremental.cursor_context import with_active_incremental_cursor
from port_ocean.context.ocean import ocean
from port_ocean.context.resource import resource_context
from integration import GithubPortAppConfig


async def _aiter_one(value: Any) -> AsyncGenerator[List[Dict[str, Any]], None]:
    yield value


@pytest.fixture
def github_main(mock_ocean_context: None) -> Any:
    with (
        patch.object(
            ocean.app.integration,
            "on_start",
            side_effect=lambda function: function,
        ),
        patch.object(
            ocean.app.integration,
            "on_resync",
            side_effect=lambda function, _: function,
        ),
        patch.object(
            ocean.app.integration,
            "on_incremental_resync",
            side_effect=lambda function, _: function,
        ),
    ):
        return importlib.import_module("main")


@pytest.mark.asyncio
async def test_folder_pattern_mapping_builder_all_repos() -> None:
    org_exporter = MagicMock()
    repo_exporter = MagicMock()

    # orgs → one org
    org_exporter.get_paginated_resources = lambda *args, **kwargs: _aiter_one(
        [{"login": "test-org", "type": "Organization"}]
    )

    # repos → two repos with default branches
    repo_exporter.get_paginated_resources = lambda *args, **kwargs: _aiter_one(
        [
            {"name": "repo1", "default_branch": "main"},
            {"name": "repo2", "default_branch": "develop"},
        ]
    )

    builder = FolderPatternMappingBuilder(org_exporter, repo_exporter, repo_type="all")

    selectors = [FolderSelector(organization="test-org", path="src/**", repos=None)]
    async with event_context("test_event") as event:
        event.port_app_config = GithubPortAppConfig(repository_type="all", resources=[])
        result = await builder.build(selectors)

    # Validate structure
    assert isinstance(result, list)
    assert len(result) == 2

    repos = {(opt["organization"], opt["repo_name"]): opt for opt in result}
    assert ("test-org", "repo1") in repos
    assert ("test-org", "repo2") in repos

    repo1_items = repos[("test-org", "repo1")]["folders"]
    assert repo1_items[0]["path"] == "src/**"
    assert repo1_items[0]["branch"] == "main"

    repo2_items = repos[("test-org", "repo2")]["folders"]
    assert repo2_items[0]["branch"] == "develop"


@pytest.mark.asyncio
async def test_folder_pattern_mapping_builder_explicit_repos() -> None:
    org_exporter = MagicMock()
    repo_exporter = MagicMock()

    org_exporter.get_paginated_resources = lambda *args, **kwargs: _aiter_one(
        [{"login": "test-org", "type": "Organization"}]
    )

    # Exact selector path calls get_repository_metadata via repo_selectors
    with patch(
        "github.helpers.repo_selectors.get_repository_metadata",
        new=AsyncMock(return_value={"default_branch": "main", "name": "repoX"}),
    ):
        builder = FolderPatternMappingBuilder(
            org_exporter,
            repo_exporter,
            repo_type="all",
        )

        selectors = [
            FolderSelector(
                organization="test-org",
                path="docs",
                repos=[RepositoryBranchMapping(name="repoX", branch=None)],
            )
        ]

        async with event_context("test_event") as event:
            event.port_app_config = GithubPortAppConfig(
                repository_type="all", resources=[]
            )
            result = await builder.build(selectors)
        assert len(result) == 1
        opt = result[0]
        assert opt["organization"] == "test-org"
        assert opt["repo_name"] == "repoX"
        assert opt["folders"][0]["path"] == "docs"
        # Branch fallback to default_branch from metadata
        assert opt["folders"][0]["branch"] == "main"


@pytest.mark.asyncio
async def test_resync_folders_skips_inaccessible_organizations(
    github_main: Any,
) -> None:
    allowed_folder = MagicMock(organization="allowed", included_files=[])
    denied_folder = MagicMock(organization="denied", included_files=[])
    folder_exporter = MagicMock()
    folder_exporter.get_paginated_resources.return_value = _aiter_one([{"id": "1"}])
    pattern_builder = MagicMock(build=AsyncMock(return_value=[]))
    authenticator = MagicMock(organization="allowed")

    with (
        patch.object(github_main, "create_github_client", return_value=MagicMock()),
        patch.object(
            github_main,
            "get_auth_provider",
            return_value=MagicMock(
                list_authenticators=AsyncMock(return_value=[authenticator])
            ),
        ),
        patch.object(github_main, "RestFolderExporter", return_value=folder_exporter),
        patch.object(
            github_main,
            "FolderPatternMappingBuilder",
            return_value=pattern_builder,
        ),
    ):
        async with event_context("test_event") as event:
            event.port_app_config = MagicMock(repository_type="all")
            async with resource_context(
                MagicMock(
                    kind="folder",
                    selector=MagicMock(
                        folders=[allowed_folder, denied_folder],
                        included_files=[],
                    ),
                )
            ):
                batches = [
                    batch async for batch in github_main.resync_folders("folder")
                ]

    assert batches == [[{"id": "1"}]]
    pattern_builder.build.assert_awaited_once_with([allowed_folder], updated_since=None)


@pytest.mark.asyncio
async def test_resync_files_skips_inaccessible_organizations(
    github_main: Any,
) -> None:
    allowed_file = MagicMock(organization="allowed")
    denied_file = MagicMock(organization="denied")
    file_exporter = MagicMock()
    file_exporter.get_paginated_resources.return_value = _aiter_one([{"path": "a.yml"}])
    pattern_builder = MagicMock(build=AsyncMock(return_value=[]))
    authenticator = MagicMock(organization="allowed")

    with (
        patch.object(github_main, "create_github_client", return_value=MagicMock()),
        patch.object(
            github_main,
            "get_auth_provider",
            return_value=MagicMock(
                list_authenticators=AsyncMock(return_value=[authenticator])
            ),
        ),
        patch.object(github_main, "RestFileExporter", return_value=file_exporter),
        patch.object(
            github_main,
            "FilePatternMappingBuilder",
            return_value=pattern_builder,
        ),
    ):
        async with event_context("test_event") as event:
            event.port_app_config = MagicMock(repository_type="all")
            async with resource_context(
                MagicMock(
                    kind="file",
                    selector=MagicMock(
                        files=[allowed_file, denied_file],
                        included_files=[],
                    ),
                )
            ):
                batches = [batch async for batch in github_main.resync_files("file")]

    assert batches == [[{"path": "a.yml"}]]
    pattern_builder.build.assert_awaited_once_with([allowed_file], updated_since=None)


@pytest.mark.asyncio
async def test_resync_folders_routes_selectors_to_matching_authenticators(
    github_main: Any,
) -> None:
    first_folder = MagicMock(organization="first", included_files=[])
    second_folder = MagicMock(organization="second", included_files=[])
    first_authenticator = MagicMock(organization="first")
    second_authenticator = MagicMock(organization="second")
    folder_exporter = MagicMock()
    folder_exporter.get_paginated_resources.return_value = _aiter_one([])
    first_builder = MagicMock(build=AsyncMock(return_value=[]))
    second_builder = MagicMock(build=AsyncMock(return_value=[]))

    with (
        patch.object(
            github_main,
            "create_github_client",
            return_value=MagicMock(),
        ) as create_client,
        patch.object(
            github_main,
            "get_auth_provider",
            return_value=MagicMock(
                list_authenticators=AsyncMock(
                    return_value=[first_authenticator, second_authenticator]
                )
            ),
        ),
        patch.object(github_main, "RestFolderExporter", return_value=folder_exporter),
        patch.object(
            github_main,
            "FolderPatternMappingBuilder",
            side_effect=[first_builder, second_builder],
        ),
    ):
        async with event_context("test_event") as event:
            event.port_app_config = MagicMock(repository_type="all")
            async with resource_context(
                MagicMock(
                    kind="folder",
                    selector=MagicMock(
                        folders=[first_folder, second_folder],
                        included_files=[],
                    ),
                )
            ):
                _ = [batch async for batch in github_main.resync_folders("folder")]

    assert {call.args[0].organization for call in create_client.call_args_list} == {
        "first",
        "second",
    }
    assert {
        tuple(call.args[0])
        for builder in (first_builder, second_builder)
        for call in builder.build.await_args_list
    } == {
        (first_folder,),
        (second_folder,),
    }


@pytest.mark.asyncio
async def test_resync_files_routes_selectors_to_matching_authenticators(
    github_main: Any,
) -> None:
    first_file = MagicMock(organization="first")
    second_file = MagicMock(organization="second")
    first_authenticator = MagicMock(organization="first")
    second_authenticator = MagicMock(organization="second")
    file_exporter = MagicMock()
    file_exporter.get_paginated_resources.return_value = _aiter_one([])
    first_builder = MagicMock(build=AsyncMock(return_value=[]))
    second_builder = MagicMock(build=AsyncMock(return_value=[]))

    with (
        patch.object(
            github_main,
            "create_github_client",
            return_value=MagicMock(),
        ) as create_client,
        patch.object(
            github_main,
            "get_auth_provider",
            return_value=MagicMock(
                list_authenticators=AsyncMock(
                    return_value=[first_authenticator, second_authenticator]
                )
            ),
        ),
        patch.object(github_main, "RestFileExporter", return_value=file_exporter),
        patch.object(
            github_main,
            "FilePatternMappingBuilder",
            side_effect=[first_builder, second_builder],
        ),
    ):
        async with event_context("test_event") as event:
            event.port_app_config = MagicMock(repository_type="all")
            async with resource_context(
                MagicMock(
                    kind="file",
                    selector=MagicMock(
                        files=[first_file, second_file],
                        included_files=[],
                    ),
                )
            ):
                _ = [batch async for batch in github_main.resync_files("file")]

    assert {call.args[0].organization for call in create_client.call_args_list} == {
        "first",
        "second",
    }
    assert {
        tuple(call.args[0])
        for builder in (first_builder, second_builder)
        for call in builder.build.await_args_list
    } == {
        (first_file,),
        (second_file,),
    }


@pytest.mark.asyncio
async def test_folder_pattern_mapping_builder_lists_pushed_repos_once() -> None:
    org_exporter = MagicMock()
    org_exporter.get_paginated_resources = lambda *args, **kwargs: _aiter_one(
        [{"login": "test-org", "type": "Organization"}]
    )
    list_calls: List[Dict[str, Any]] = []

    def list_repos(options: Dict[str, Any]) -> AsyncGenerator[Any, None]:
        list_calls.append(options)
        return _aiter_one([{"name": "repo1", "default_branch": "main"}])

    repo_exporter = MagicMock()
    repo_exporter.get_paginated_resources = list_repos
    pushed_since = datetime(2026, 10, 1, tzinfo=timezone.utc)

    builder = FolderPatternMappingBuilder(org_exporter, repo_exporter, repo_type="all")
    selectors = [
        FolderSelector(organization="test-org", path="services/*"),
        FolderSelector(organization="test-org", path="libs/*"),
    ]
    async with event_context("test_event") as event:
        event.port_app_config = GithubPortAppConfig(repository_type="all", resources=[])
        result = await builder.build(selectors, updated_since=pushed_since)

    assert len(list_calls) == 1
    assert list_calls[0]["pushed_since"] == pushed_since
    assert [f["path"] for f in result[0]["folders"]] == ["services/*", "libs/*"]


@pytest.mark.asyncio
async def test_resync_folders_passes_incremental_cursor(github_main: Any) -> None:
    cursor = datetime(2026, 10, 1, tzinfo=timezone.utc)
    folder = MagicMock(organization="allowed", included_files=[])
    folder_exporter = MagicMock()
    folder_exporter.get_paginated_resources.return_value = _aiter_one([])
    pattern_builder = MagicMock(build=AsyncMock(return_value=[]))

    with (
        patch.object(github_main, "create_github_client", return_value=MagicMock()),
        patch.object(
            github_main,
            "get_auth_provider",
            return_value=MagicMock(
                list_authenticators=AsyncMock(
                    return_value=[MagicMock(organization="allowed")]
                )
            ),
        ),
        patch.object(github_main, "RestFolderExporter", return_value=folder_exporter),
        patch.object(
            github_main, "FolderPatternMappingBuilder", return_value=pattern_builder
        ),
        with_active_incremental_cursor(cursor),
    ):
        async with event_context("test_event") as event:
            event.port_app_config = MagicMock(repository_type="all")
            async with resource_context(
                MagicMock(
                    kind="folder",
                    selector=MagicMock(folders=[folder], included_files=[]),
                )
            ):
                [batch async for batch in github_main.resync_folders("folder")]

    pattern_builder.build.assert_awaited_once_with([folder], updated_since=cursor)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cursor",
    [None, datetime(2026, 10, 1, tzinfo=timezone.utc)],
    ids=["full-resync", "incremental"],
)
async def test_resync_skills_passes_cursor_to_builder(
    github_main: Any, cursor: datetime | None
) -> None:
    skill_path = MagicMock(
        path=".claude/skills/**/SKILL.md",
        organization="allowed",
        repos=None,
        exclude_archived=False,
    )
    skill_exporter = MagicMock()
    skill_exporter.get_paginated_resources.return_value = _aiter_one([{"skill": {}}])
    pattern_builder = MagicMock(build=AsyncMock(return_value=[]))

    with (
        patch.object(github_main, "create_github_client", return_value=MagicMock()),
        patch.object(
            github_main,
            "get_auth_provider",
            return_value=MagicMock(
                list_authenticators=AsyncMock(
                    return_value=[MagicMock(organization="allowed")]
                )
            ),
        ),
        patch.object(github_main, "SkillExporter", return_value=skill_exporter),
        patch.object(
            github_main, "FilePatternMappingBuilder", return_value=pattern_builder
        ),
    ):
        async with event_context("test_event") as event:
            event.port_app_config = MagicMock(repository_type="all")
            async with resource_context(
                MagicMock(kind="skill", selector=MagicMock(paths=[skill_path]))
            ):
                if cursor:
                    with with_active_incremental_cursor(cursor):
                        batches = [b async for b in github_main.resync_skills("skill")]
                else:
                    batches = [b async for b in github_main.resync_skills("skill")]

    assert batches == [[{"skill": {}}]]
    pattern_builder.build.assert_awaited_once()
    assert pattern_builder.build.await_args is not None
    file_patterns = pattern_builder.build.await_args.args[0]
    assert [p.path for p in file_patterns] == [".claude/skills/**/SKILL.md"]
    assert pattern_builder.build.await_args.kwargs == {"updated_since": cursor}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cursor",
    [None, datetime(2026, 10, 1, tzinfo=timezone.utc)],
    ids=["full-resync", "incremental"],
)
async def test_resync_plugins_lists_pushed_repos_once(
    github_main: Any, cursor: datetime | None
) -> None:
    list_calls: List[Dict[str, Any]] = []

    def list_repos(options: Dict[str, Any]) -> AsyncGenerator[Any, None]:
        list_calls.append(options)
        return _aiter_one([{"name": "repo1", "default_branch": "main"}])

    org_exporter = MagicMock()
    org_exporter.get_paginated_resources = lambda *args, **kwargs: _aiter_one(
        [{"login": "allowed", "type": "Organization"}]
    )
    repo_exporter = MagicMock()
    repo_exporter.get_paginated_resources = list_repos
    plugin_exporter = MagicMock()
    plugin_exporter.get_paginated_resources = MagicMock(
        side_effect=lambda options: _aiter_one([{"plugin": {"name": "p"}}])
    )
    paths = [
        RepositorySourceModel.parse_obj({"organization": "allowed"}),
        RepositorySourceModel.parse_obj({"organization": "allowed"}),
    ]

    with (
        patch.object(github_main, "create_github_client", return_value=MagicMock()),
        patch.object(
            github_main,
            "get_auth_provider",
            return_value=MagicMock(
                list_authenticators=AsyncMock(
                    return_value=[MagicMock(organization="allowed")]
                )
            ),
        ),
        patch.object(
            github_main, "RestOrganizationExporter", return_value=org_exporter
        ),
        patch.object(github_main, "RestRepositoryExporter", return_value=repo_exporter),
        patch.object(github_main, "PluginExporter", return_value=plugin_exporter),
    ):
        async with event_context("test_event") as event:
            event.port_app_config = MagicMock(repository_type="all")
            async with resource_context(
                MagicMock(
                    kind="plugin",
                    selector=MagicMock(paths=paths, providers=["claude"]),
                )
            ):
                if cursor:
                    with with_active_incremental_cursor(cursor):
                        batches = [
                            b async for b in github_main.resync_plugins("plugin")
                        ]
                else:
                    batches = [b async for b in github_main.resync_plugins("plugin")]

    # Both path entries reuse a single org listing.
    assert len(list_calls) == 1
    assert list_calls[0].get("pushed_since") == cursor
    assert batches == [[{"plugin": {"name": "p"}}], [{"plugin": {"name": "p"}}]]
    repositories = plugin_exporter.get_paginated_resources.call_args.args[0][
        "repositories"
    ]
    assert [(r["repository"]["name"], r["branch"]) for r in repositories] == [
        ("repo1", "main")
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cursor",
    [None, datetime(2026, 10, 1, tzinfo=timezone.utc)],
    ids=["full-resync", "incremental"],
)
async def test_resync_mcp_passes_cursor_to_builder(
    github_main: Any, cursor: datetime | None
) -> None:
    mcp_path = MagicMock(
        path=".mcp.json", organization="allowed", repos=None, exclude_archived=False
    )
    mcp_exporter = MagicMock()
    mcp_exporter.get_paginated_resources.return_value = _aiter_one([{"server": {}}])
    pattern_builder = MagicMock(build=AsyncMock(return_value=[]))

    with (
        patch.object(github_main, "create_github_client", return_value=MagicMock()),
        patch.object(
            github_main,
            "get_auth_provider",
            return_value=MagicMock(
                list_authenticators=AsyncMock(
                    return_value=[MagicMock(organization="allowed")]
                )
            ),
        ),
        patch.object(github_main, "McpExporter", return_value=mcp_exporter),
        patch.object(
            github_main, "FilePatternMappingBuilder", return_value=pattern_builder
        ),
    ):
        async with event_context("test_event") as event:
            event.port_app_config = MagicMock(repository_type="all")
            async with resource_context(
                MagicMock(kind="mcp", selector=MagicMock(paths=[mcp_path]))
            ):
                if cursor:
                    with with_active_incremental_cursor(cursor):
                        batches = [b async for b in github_main.resync_mcp("mcp")]
                else:
                    batches = [b async for b in github_main.resync_mcp("mcp")]

    assert batches == [[{"server": {}}]]
    pattern_builder.build.assert_awaited_once()
    assert pattern_builder.build.await_args is not None
    file_patterns = pattern_builder.build.await_args.args[0]
    assert [p.path for p in file_patterns] == [".mcp.json"]
    assert pattern_builder.build.await_args.kwargs == {"updated_since": cursor}
