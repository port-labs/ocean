import pytest
from unittest.mock import MagicMock
from collections import namedtuple

from github.core.exporters.file_exporter.utils import group_file_patterns_by_repositories_in_selector

# Mocking GithubFilePattern as it's not available in test context directly
GithubFilePattern = namedtuple("GithubFilePattern", ["path", "skip_parsing", "repos"])


@pytest.mark.asyncio
async def test_group_file_patterns_by_repositories_in_selector_no_repos_specified():
    """
    Test that when a file selector has no repositories specified, it defaults to all available repositories from the exporter.
    """
    # Arrange
    mock_file_pattern = GithubFilePattern(
        path="**/*.yaml", skip_parsing=False, repos=None
    )
    files = [mock_file_pattern]

    repo_exporter = MagicMock()

    async def mock_paginated_resources(*args, **kwargs):
        yield [
            {"name": "repo1", "default_branch": "main"},
            {"name": "repo2", "default_branch": "master"},
        ]

    repo_exporter.get_paginated_resources = mock_paginated_resources

    repo_type = "private"

    # Act
    result = await group_file_patterns_by_repositories_in_selector(
        files, repo_exporter, repo_type
    )

    # Assert
    assert len(result) == 2

    repo1_result = next(item for item in result if item["repo_name"] == "repo1")
    repo1_files = repo1_result["files"]
    assert repo1_files[0]["path"] == "**/*.yaml"
    assert repo1_files[0]["branch"] == "main"
    assert repo1_files[0]["skip_parsing"] is False

    repo2_result = next(item for item in result if item["repo_name"] == "repo2")
    repo2_files = repo2_result["files"]
    assert repo2_files[0]["path"] == "**/*.yaml"
    assert repo2_files[0]["branch"] == "master"
    assert repo2_files[0]["skip_parsing"] is False
