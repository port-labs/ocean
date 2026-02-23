import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest

from github.enrichments.included_files.fetcher import (
    IncludedFileFetchKey,
    IncludedFilesFetcher,
)
from github.enrichments.included_files.utils import (
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
                repo_name="Port",
                branch="main",
                default_branch="main",
            )
            is True
        )
        assert (
            repo_branch_matches(
                repos=None,
                repo_name="Port",
                branch="dev",
                default_branch="main",
            )
            is False
        )

    def test_explicit_branch_mapping(self) -> None:
        repos = [RepositoryBranchMapping(name="Port", branch="dev")]
        assert (
            repo_branch_matches(
                repos=repos,
                repo_name="Port",
                branch="dev",
                default_branch="main",
            )
            is True
        )
        assert (
            repo_branch_matches(
                repos=repos,
                repo_name="Port",
                branch="main",
                default_branch="main",
            )
            is False
        )

    def test_none_branch_mapping_means_default_branch(self) -> None:
        repos = [RepositoryBranchMapping(name="Port", branch=None)]
        assert (
            repo_branch_matches(
                repos=repos,
                repo_name="Port",
                branch="main",
                default_branch="main",
            )
            is True
        )
        assert (
            repo_branch_matches(
                repos=repos,
                repo_name="Port",
                branch="dev",
                default_branch="main",
            )
            is False
        )


@pytest.mark.asyncio
class TestIncludedFilesFetcher:
    async def test_inflight_dedup_and_results_cache(self) -> None:
        org = "test-org"
        repo = "test-repo"
        branch = "main"
        file_path = "README.md"

        key = IncludedFileFetchKey(
            organization=org,
            repo_name=repo,
            branch=branch,
            file_path=file_path,
        )

        mock_file_exporter = AsyncMock()
        gate = asyncio.Event()
        called = asyncio.Event()

        async def get_resource_side_effect(_options: dict[str, Any]) -> dict[str, Any]:
            called.set()
            await gate.wait()
            return {"content": "hello"}

        mock_file_exporter.get_resource.side_effect = get_resource_side_effect

        with patch(
            "github.enrichments.included_files.fetcher.RestFileExporter",
            return_value=mock_file_exporter,
        ):
            fetcher = IncludedFilesFetcher(client=MagicMock())

            t1 = asyncio.create_task(fetcher.get(key))
            t2 = asyncio.create_task(fetcher.get(key))

            # Wait until the underlying exporter is actually called.
            await asyncio.wait_for(called.wait(), timeout=1)

            # Only one underlying request should be in-flight for the same key.
            assert mock_file_exporter.get_resource.call_count == 1

            gate.set()
            r1, r2 = await asyncio.gather(t1, t2)
            assert r1 == "hello"
            assert r2 == "hello"

            # Cached: no additional exporter call.
            r3 = await fetcher.get(key)
            assert r3 == "hello"
            assert mock_file_exporter.get_resource.call_count == 1
