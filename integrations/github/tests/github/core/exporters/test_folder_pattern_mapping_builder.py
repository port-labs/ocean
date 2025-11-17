from typing import Any, AsyncGenerator, Dict, List

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from github.core.exporters.folder_exporter.utils import FolderPatternMappingBuilder
from integration import FolderSelector, RepositoryBranchMapping


async def _aiter_one(value: Any) -> AsyncGenerator[List[Dict[str, Any]], None]:
    yield value


@pytest.mark.asyncio
async def test_folder_pattern_mapping_builder_all_repos() -> None:
    org_exporter = MagicMock()
    repo_exporter = MagicMock()

    # orgs → one org
    org_exporter.get_paginated_resources = lambda *args, **kwargs: _aiter_one(
        [{"login": "test-org"}]
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
        [{"login": "test-org"}]
    )

    # Exact selector path calls get_repository_metadata via repo_selectors
    with patch(
        "github.helpers.repo_selectors.get_repository_metadata",
        new=AsyncMock(return_value={"default_branch": "main", "name": "repoX"}),
    ):
        builder = FolderPatternMappingBuilder(
            org_exporter, repo_exporter, repo_type="all"
        )

        selectors = [
            FolderSelector(
                organization="test-org",
                path="docs",
                repos=[RepositoryBranchMapping(name="repoX", branch=None)],
            )
        ]

        result = await builder.build(selectors)
        assert len(result) == 1
        opt = result[0]
        assert opt["organization"] == "test-org"
        assert opt["repo_name"] == "repoX"
        assert opt["folders"][0]["path"] == "docs"
        # Branch fallback to default_branch from metadata
        assert opt["folders"][0]["branch"] == "main"
