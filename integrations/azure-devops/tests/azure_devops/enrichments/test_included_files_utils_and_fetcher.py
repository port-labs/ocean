import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from azure_devops.enrichments.included_files.fetcher import (
    IncludedFileFetchKey,
    IncludedFilesFetcher,
)
from azure_devops.enrichments.included_files.utils import (
    repo_branch_matches,
    resolve_included_file_path,
)
from azure_devops.misc import RepositoryBranchMapping


class TestResolveIncludedFilePath:
    def test_repo_root_leading_slash_when_no_base(self) -> None:
        assert resolve_included_file_path("/README.md", base_path="") == "README.md"

    def test_relative_to_base_when_base_present(self) -> None:
        assert (
            resolve_included_file_path("README.md", base_path="remote")
            == "remote/README.md"
        )

    def test_does_not_double_join_when_requested_already_includes_base(self) -> None:
        assert (
            resolve_included_file_path("remote/README.md", base_path="remote")
            == "remote/README.md"
        )
        assert (
            resolve_included_file_path("/remote/README.md", base_path="remote")
            == "remote/README.md"
        )


class TestRepoBranchMatches:
    def test_default_branch_only_when_no_repos_mapping(self) -> None:
        assert (
            repo_branch_matches(
                repos=None,
                repo_name="test-repo",
                branch="main",
                default_branch="main",
            )
            is True
        )
        assert (
            repo_branch_matches(
                repos=None,
                repo_name="test-repo",
                branch="dev",
                default_branch="main",
            )
            is False
        )

    def test_explicit_branch_mapping(self) -> None:
        repos = [RepositoryBranchMapping(name="test-repo", branch="dev")]
        assert (
            repo_branch_matches(
                repos=repos,
                repo_name="test-repo",
                branch="dev",
                default_branch="main",
            )
            is True
        )
        assert (
            repo_branch_matches(
                repos=repos,
                repo_name="test-repo",
                branch="main",
                default_branch="main",
            )
            is False
        )

    def test_none_branch_mapping_means_default_branch(self) -> None:
        repos = [RepositoryBranchMapping(name="test-repo", branch=None)]
        assert (
            repo_branch_matches(
                repos=repos,
                repo_name="test-repo",
                branch="main",
                default_branch="main",
            )
            is True
        )
        assert (
            repo_branch_matches(
                repos=repos,
                repo_name="test-repo",
                branch="dev",
                default_branch="main",
            )
            is False
        )


@pytest.mark.asyncio
class TestIncludedFilesFetcher:
    async def test_inflight_dedup_and_results_cache(self) -> None:
        project_id = "project-1"
        repo_id = "repo-123"
        repo_name = "test-repo"
        branch = "main"
        file_path = "README.md"

        key = IncludedFileFetchKey(
            project_id=project_id,
            repo_id=repo_id,
            repo_name=repo_name,
            branch=branch,
            file_path=file_path,
        )

        mock_client = MagicMock()
        gate = asyncio.Event()
        called = asyncio.Event()

        async def get_file_by_branch_side_effect(
            _path: str, _repo_id: str, _branch: str
        ) -> bytes:
            called.set()
            await gate.wait()
            return b"hello"

        mock_client.get_file_by_branch = AsyncMock(
            side_effect=get_file_by_branch_side_effect
        )

        fetcher = IncludedFilesFetcher(client=mock_client)

        t1 = asyncio.create_task(fetcher.get(key))
        t2 = asyncio.create_task(fetcher.get(key))

        # Wait until the underlying client is actually called.
        await asyncio.wait_for(called.wait(), timeout=1)

        # Only one underlying request should be in-flight for the same key.
        assert mock_client.get_file_by_branch.call_count == 1

        gate.set()
        r1, r2 = await asyncio.gather(t1, t2)
        assert r1 == "hello"
        assert r2 == "hello"

        # Cached: no additional client call.
        r3 = await fetcher.get(key)
        assert r3 == "hello"
        assert mock_client.get_file_by_branch.call_count == 1

    async def test_fetcher_handles_missing_file(self) -> None:
        mock_client = MagicMock()
        mock_client.get_file_by_branch = AsyncMock(
            side_effect=Exception("404 Not Found")
        )

        fetcher = IncludedFilesFetcher(client=mock_client)
        key = IncludedFileFetchKey(
            project_id="project-1",
            repo_id="repo-123",
            repo_name="test-repo",
            branch="main",
            file_path="MISSING.md",
        )

        result = await fetcher.get(key)
        assert result is None

    async def test_fetcher_decodes_bytes(self) -> None:
        mock_client = MagicMock()
        mock_client.get_file_by_branch = AsyncMock(
            return_value="héllo wörld".encode("utf-8")
        )

        fetcher = IncludedFilesFetcher(client=mock_client)
        key = IncludedFileFetchKey(
            project_id="project-1",
            repo_id="repo-123",
            repo_name="test-repo",
            branch="main",
            file_path="file.txt",
        )

        result = await fetcher.get(key)
        assert result == "héllo wörld"

    async def test_fetcher_handles_empty_bytes(self) -> None:
        mock_client = MagicMock()
        mock_client.get_file_by_branch = AsyncMock(return_value=b"")

        fetcher = IncludedFilesFetcher(client=mock_client)
        key = IncludedFileFetchKey(
            project_id="project-1",
            repo_id="repo-123",
            repo_name="test-repo",
            branch="main",
            file_path="empty.txt",
        )

        result = await fetcher.get(key)
        assert result == ""
