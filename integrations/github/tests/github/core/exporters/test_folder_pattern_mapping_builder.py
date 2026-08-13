import importlib
from typing import Any, AsyncGenerator, Dict, List

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from github.core.exporters.folder_exporter.utils import FolderPatternMappingBuilder
from integration import FolderSelector, RepositoryBranchMapping
from port_ocean.context.event import event_context
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
    pattern_builder.build.assert_awaited_once_with([allowed_folder])


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
    pattern_builder.build.assert_awaited_once_with([allowed_file])


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
