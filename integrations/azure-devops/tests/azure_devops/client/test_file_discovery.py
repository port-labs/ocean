"""Tests for AzureDevopsClient file discovery behaviour."""

from typing import Any, AsyncGenerator

import pytest

from azure_devops.client.azure_devops_client import AzureDevopsClient


@pytest.mark.asyncio
async def test_generate_files_does_not_stop_after_empty_project() -> None:
    """Regression test for PORT-17439.

    When generate_repositories yields an empty batch (a project with no repos),
    generate_files must skip it and continue processing subsequent batches.
    """
    client = AzureDevopsClient("https://dev.azure.com/test", "token")

    mock_repo = {
        "name": "repo1",
        "id": "repo1-id",
        "defaultBranch": "refs/heads/main",
        "project": {"id": "project2-id"},
    }
    mock_file = {"file": {"path": "README.md"}, "repo": mock_repo}

    async def mock_generate_repositories(
        include_disabled_repositories: bool = True,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield []  # empty project — must NOT stop processing
        yield [mock_repo]

    async def mock_get_repository_files(
        repository: dict[str, Any], paths: list[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [mock_file]

    client.generate_repositories = mock_generate_repositories  # type: ignore
    client._get_repository_files = mock_get_repository_files  # type: ignore

    results = []
    async for batch in client.generate_files(["**/*.md"]):
        results.extend(batch)

    assert len(results) == 1
    assert results[0]["repo"]["name"] == "repo1"
