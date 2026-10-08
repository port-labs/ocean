import asyncio
from typing import Sequence, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import HTTPStatusError

from bitbucket_cloud.client import BitbucketClient
from bitbucket_cloud.enrichments.included_files.enricher import (
    IncludedFilesEnricher,
)
from bitbucket_cloud.enrichments.included_files.strategies import (
    FileIncludedFilesStrategy,
)
from bitbucket_cloud.enrichments.included_files.fetcher import (
    IncludedFileFetchKey,
    IncludedFilesFetcher,
)
from bitbucket_cloud.enrichments.included_files.utils import (
    RepoBranchMappingLike,
    repo_branch_matches,
    resolve_included_file_path,
)
from integration import RepositoryBranchMapping


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
                repos=cast(Sequence[RepoBranchMappingLike], repos),
                repo_name="test-repo",
                branch="dev",
                default_branch="main",
            )
            is True
        )
        assert (
            repo_branch_matches(
                repos=cast(Sequence[RepoBranchMappingLike], repos),
                repo_name="test-repo",
                branch="main",
                default_branch="main",
            )
            is False
        )

    def test_default_branch_mapping_means_default_branch(self) -> None:
        # When branch is "default", it matches the default_branch
        repos = [RepositoryBranchMapping(name="test-repo", branch="default")]
        assert (
            repo_branch_matches(
                repos=cast(Sequence[RepoBranchMappingLike], repos),
                repo_name="test-repo",
                branch="main",
                default_branch="main",
            )
            is True
        )
        assert (
            repo_branch_matches(
                repos=cast(Sequence[RepoBranchMappingLike], repos),
                repo_name="test-repo",
                branch="dev",
                default_branch="main",
            )
            is False
        )


@pytest.mark.asyncio
class TestIncludedFilesFetcher:
    async def test_inflight_dedup_and_results_cache(self) -> None:
        repo_slug = "test-repo"
        branch = "main"
        file_path = "README.md"

        key = IncludedFileFetchKey(
            workspace="test-workspace",
            repo_slug=repo_slug,
            repo_name="test-repo",
            branch=branch,
            file_path=file_path,
        )

        mock_client = MagicMock()
        gate = asyncio.Event()
        called = asyncio.Event()

        async def get_repository_files_side_effect(
            _slug: str, _branch: str, _path: str
        ) -> str:
            called.set()
            await gate.wait()
            return "hello"

        mock_client.get_repository_files = AsyncMock(
            side_effect=get_repository_files_side_effect
        )

        fetcher = IncludedFilesFetcher(client=mock_client)

        t1 = asyncio.create_task(fetcher.get(key))
        t2 = asyncio.create_task(fetcher.get(key))

        # Wait until the underlying client is actually called.
        await asyncio.wait_for(called.wait(), timeout=1)

        # Only one underlying request should be in-flight for the same key.
        assert mock_client.get_repository_files.call_count == 1

        gate.set()
        r1, r2 = await asyncio.gather(t1, t2)
        assert r1 == "hello"
        assert r2 == "hello"

        # Cached: no additional client call.
        r3 = await fetcher.get(key)
        assert r3 == "hello"
        assert mock_client.get_repository_files.call_count == 1

    async def test_fetcher_handles_missing_file(self) -> None:
        mock_client = MagicMock()
        mock_client.get_repository_files = AsyncMock(
            side_effect=Exception("404 Not Found")
        )

        fetcher = IncludedFilesFetcher(client=mock_client)
        key = IncludedFileFetchKey(
            workspace="test-workspace",
            repo_slug="test-repo",
            repo_name="test-repo",
            branch="main",
            file_path="MISSING.md",
        )

        result = await fetcher.get(key)
        assert result is None

    async def test_fetcher_handles_string_content(self) -> None:
        mock_client = MagicMock()
        mock_client.get_repository_files = AsyncMock(return_value="file content")

        fetcher = IncludedFilesFetcher(client=mock_client)
        key = IncludedFileFetchKey(
            workspace="test-workspace",
            repo_slug="test-repo",
            repo_name="test-repo",
            branch="main",
            file_path="file.txt",
        )

        result = await fetcher.get(key)
        assert result == "file content"

    async def test_fetcher_handles_empty_string(self) -> None:
        mock_client = MagicMock()
        mock_client.get_repository_files = AsyncMock(return_value="")

        fetcher = IncludedFilesFetcher(client=mock_client)
        key = IncludedFileFetchKey(
            workspace="test-workspace",
            repo_slug="test-repo",
            repo_name="test-repo",
            branch="main",
            file_path="empty.txt",
        )

        result = await fetcher.get(key)
        assert result == ""


class TestFileIncludedFilesStrategy:
    """The file kind emits no top-level `path`, so includedFiles resolve from the repo root.

    Adding a `path` key to the emitted object would silently relocate every configured
    includedFiles path to the matched file's directory instead.
    """

    def test_base_path_is_repo_root_without_a_path_key(self) -> None:
        from bitbucket_cloud.enrichments.included_files.strategies import (
            FileIncludedFilesStrategy,
        )

        strategy = FileIncludedFilesStrategy(included_files=["docs/service.md"])
        entity = {
            "content": "",
            "metadata": {"path": "charts/app/port.yml"},
            "repo": {"slug": "repo", "name": "Repo"},
            "branch": "main",
        }

        ctx = strategy.context_for(entity)

        assert ctx.base_path == "."
        assert (
            resolve_included_file_path("docs/service.md", base_path=ctx.base_path)
            == "docs/service.md"
        )


class TestIncludedFilesAgainstTheClientContract:
    """`__includedFiles` holds null for a file Bitbucket does not have, not "".

    Driven through the real client's 404 path, so the assertion is about the contract
    get_repository_files hands back rather than about a stubbed return value.
    """

    @staticmethod
    def _client_that_404s() -> BitbucketClient:
        client = BitbucketClient(
            workspace="test_workspace",
            host="https://api.bitbucket.org/2.0",
            username="test_user",
            app_password="test_password",
        )
        not_found = MagicMock()
        not_found.raise_for_status.side_effect = HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock(status_code=404)
        )
        client.client = MagicMock()
        client.client.request = AsyncMock(return_value=not_found)
        client.client.headers = {}
        return client

    @pytest.mark.asyncio
    async def test_fetcher_returns_none_for_a_missing_file(self) -> None:
        fetcher = IncludedFilesFetcher(client=self._client_that_404s())
        key = IncludedFileFetchKey(
            workspace="test_workspace",
            repo_slug="repo",
            repo_name="Repo",
            branch="main",
            file_path="gone.md",
        )

        assert await fetcher.get(key) is None

    @pytest.mark.asyncio
    async def test_enricher_attaches_null_for_a_missing_file(self) -> None:
        enricher = IncludedFilesEnricher(
            client=self._client_that_404s(),
            strategy=FileIncludedFilesStrategy(included_files=["gone.md"]),
        )
        entities = [
            {
                "content": "",
                "metadata": {"path": "port.yml"},
                "repo": {
                    "slug": "repo",
                    "name": "Repo",
                    "mainbranch": {"name": "main"},
                },
                "branch": "main",
            }
        ]

        enriched = await enricher.enrich_batch(entities)

        assert enriched[0]["__includedFiles"] == {"gone.md": None}
