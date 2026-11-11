from github.helpers.repository_change import RepositoryChange, RepositoryChangeField
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github.core.options import ListRepositoryOptions
from github.helpers.repo_selectors import (
    RepositorySelector,
)
from integration import RepositorySourceModel


def _make_paginated_resources_mock(
    batches: List[List[Dict[str, Any]]],
) -> MagicMock:
    """Build a `get_paginated_resources`-shaped mock that yields the given batches."""

    def _side_effect(options: ListRepositoryOptions) -> AsyncIterator[Any]:
        async def _gen() -> AsyncIterator[Any]:
            for batch in batches:
                yield batch

        return _gen()

    return MagicMock(side_effect=_side_effect)


@pytest.mark.asyncio
class TestRepositorySelectorListing:
    async def test_select_repos_passes_exclude_archived_through(self) -> None:
        selector = RepositorySourceModel.parse_obj({"excludeArchived": True})
        repo_exporter = MagicMock()
        repo_exporter.get_paginated_resources = _make_paginated_resources_mock(
            [[{"name": "repo1", "default_branch": "main", "archived": False}]]
        )

        strategy = RepositorySelector("repository")
        results = [
            result
            async for result in strategy.select_repos(
                selector, repo_exporter, "test-org", "Organization"
            )
        ]

        assert results == [("repo1", "main", results[0][2])]

        repo_exporter.get_paginated_resources.assert_called_once()
        called_options = repo_exporter.get_paginated_resources.call_args.args[0]
        assert called_options["exclude_archived"] is True

    async def test_select_repos_defaults_exclude_archived_to_false(self) -> None:
        selector = RepositorySourceModel.parse_obj({})
        repo_exporter = MagicMock()
        repo_exporter.get_paginated_resources = _make_paginated_resources_mock(
            [[{"name": "repo1", "default_branch": "main", "archived": True}]]
        )

        strategy = RepositorySelector("repository")
        [
            result
            async for result in strategy.select_repos(
                selector, repo_exporter, "test-org", "Organization"
            )
        ]

        called_options = repo_exporter.get_paginated_resources.call_args.args[0]
        assert called_options["exclude_archived"] is False


@pytest.mark.asyncio
class TestRepositorySelectorExplicitRepos:
    async def test_select_repos_ignores_exclude_archived(self) -> None:
        """Explicitly listed repos are always included, regardless of the
        selector's `exclude_archived` value or the repo's own archived status -
        the same precedent already applies to `repo_search`/`search_params`.
        """
        selector = RepositorySourceModel.parse_obj(
            {
                "excludeArchived": True,
                "repos": [{"name": "explicit-repo"}],
            }
        )
        repo_exporter = MagicMock()
        repo_exporter.client = MagicMock()

        archived_repo = {
            "name": "explicit-repo",
            "default_branch": "main",
            "archived": True,
        }

        with patch(
            "github.helpers.repo_selectors.get_repository_metadata",
            new=AsyncMock(return_value=archived_repo),
        ):
            strategy = RepositorySelector("repository")
            results = [
                result
                async for result in strategy.select_repos(
                    selector, repo_exporter, "test-org", "Organization"
                )
            ]

        assert results == [("explicit-repo", "main", archived_repo)]

    async def test_select_repos_does_not_list_org_when_repos_configured(
        self,
    ) -> None:
        selector = RepositorySourceModel.parse_obj({"repos": [{"name": "explicit"}]})
        repo_exporter = MagicMock()

        with patch(
            "github.helpers.repo_selectors.get_repository_metadata",
            new=AsyncMock(return_value={"name": "explicit", "default_branch": "dev"}),
        ):
            results = [
                result[:2]
                async for result in RepositorySelector("repository").select_repos(
                    selector, repo_exporter, "test-org", "Organization"
                )
            ]

        assert results == [("explicit", "dev")]
        repo_exporter.get_paginated_resources.assert_not_called()


@pytest.mark.asyncio
class TestPushedSinceFiltering:
    async def test_all_selector_forwards_pushed_since(self) -> None:
        pushed_since = datetime(2026, 10, 1, tzinfo=timezone.utc)
        selector = RepositorySourceModel.parse_obj({})
        repo_exporter = MagicMock()
        repo_exporter.get_paginated_resources = _make_paginated_resources_mock(
            [[{"name": "repo1", "default_branch": "main"}]]
        )

        strategy = RepositorySelector("repository")
        [
            _
            async for _ in strategy.select_repos(
                selector,
                repo_exporter,
                "test-org",
                "Organization",
                RepositoryChange(pushed_since, RepositoryChangeField.PUSHED),
            )
        ]

        called_options = repo_exporter.get_paginated_resources.call_args.args[0]
        assert called_options["changed_since"] == RepositoryChange.pushed(pushed_since)

    async def test_all_selector_omits_pushed_since_on_full_resync(self) -> None:
        selector = RepositorySourceModel.parse_obj({})
        repo_exporter = MagicMock()
        repo_exporter.get_paginated_resources = _make_paginated_resources_mock([[]])

        strategy = RepositorySelector("repository")
        [
            _
            async for _ in strategy.select_repos(
                selector, repo_exporter, "test-org", "Organization"
            )
        ]

        called_options = repo_exporter.get_paginated_resources.call_args.args[0]
        assert called_options["changed_since"] is None

    async def test_exact_selector_skips_repos_not_pushed_since(self) -> None:
        pushed_since = datetime(2026, 10, 1, tzinfo=timezone.utc)
        selector = RepositorySourceModel.parse_obj(
            {"repos": [{"name": "stale"}, {"name": "fresh"}, {"name": "unknown"}]}
        )
        repo_exporter = MagicMock()
        repos = {
            "stale": {
                "name": "stale",
                "default_branch": "main",
                "pushed_at": "2026-09-01T00:00:00Z",
            },
            "fresh": {
                "name": "fresh",
                "default_branch": "main",
                "pushed_at": "2026-10-02T00:00:00Z",
            },
            "unknown": {"name": "unknown", "default_branch": "main"},
        }

        with patch(
            "github.helpers.repo_selectors.get_repository_metadata",
            new=AsyncMock(side_effect=lambda _client, _org, name: repos[name]),
        ):
            strategy = RepositorySelector("repository")
            results = [
                result[0]
                async for result in strategy.select_repos(
                    selector,
                    repo_exporter,
                    "test-org",
                    "Organization",
                    RepositoryChange(pushed_since, RepositoryChangeField.PUSHED),
                )
            ]

        assert results == ["fresh", "unknown"]
