from github.helpers.repository_change import RepositoryChange
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github.core.options import ListRepositoryOptions
from github.helpers.repo_selectors import (
    AllRepositorySelector,
    ExactRepositorySelector,
    MemoizedRepositorySelector,
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
class TestAllRepositorySelector:
    async def test_select_repos_passes_exclude_archived_through(self) -> None:
        selector = RepositorySourceModel.parse_obj({"excludeArchived": True})
        repo_exporter = MagicMock()
        repo_exporter.get_paginated_resources = _make_paginated_resources_mock(
            [[{"name": "repo1", "default_branch": "main", "archived": False}]]
        )

        strategy = AllRepositorySelector("repository")
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

        strategy = AllRepositorySelector("repository")
        [
            result
            async for result in strategy.select_repos(
                selector, repo_exporter, "test-org", "Organization"
            )
        ]

        called_options = repo_exporter.get_paginated_resources.call_args.args[0]
        assert called_options["exclude_archived"] is False


@pytest.mark.asyncio
class TestExactRepositorySelector:
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
            strategy = ExactRepositorySelector()
            results = [
                result
                async for result in strategy.select_repos(
                    selector, repo_exporter, "test-org", "Organization"
                )
            ]

        assert results == [("explicit-repo", "main", archived_repo)]

    async def test_select_repos_returns_nothing_when_no_repos_configured(
        self,
    ) -> None:
        selector = RepositorySourceModel.parse_obj({"excludeArchived": True})
        repo_exporter = MagicMock()

        strategy = ExactRepositorySelector()
        results = [
            result
            async for result in strategy.select_repos(
                selector, repo_exporter, "test-org", "Organization"
            )
        ]

        assert results == []


@pytest.mark.asyncio
class TestPushedSinceFiltering:
    async def test_all_selector_forwards_pushed_since(self) -> None:
        pushed_since = datetime(2026, 10, 1, tzinfo=timezone.utc)
        selector = RepositorySourceModel.parse_obj({})
        repo_exporter = MagicMock()
        repo_exporter.get_paginated_resources = _make_paginated_resources_mock(
            [[{"name": "repo1", "default_branch": "main"}]]
        )

        strategy = AllRepositorySelector("repository")
        [
            _
            async for _ in strategy.select_repos(
                selector,
                repo_exporter,
                "test-org",
                "Organization",
                changed_since=RepositoryChange.pushed(pushed_since),
            )
        ]

        called_options = repo_exporter.get_paginated_resources.call_args.args[0]
        assert called_options["changed_since"] == RepositoryChange.pushed(pushed_since)

    async def test_all_selector_omits_pushed_since_on_full_resync(self) -> None:
        selector = RepositorySourceModel.parse_obj({})
        repo_exporter = MagicMock()
        repo_exporter.get_paginated_resources = _make_paginated_resources_mock([[]])

        strategy = AllRepositorySelector("repository")
        [
            _
            async for _ in strategy.select_repos(
                selector, repo_exporter, "test-org", "Organization"
            )
        ]

        called_options = repo_exporter.get_paginated_resources.call_args.args[0]
        assert "changed_since" not in called_options

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
            strategy = ExactRepositorySelector()
            results = [
                result[0]
                async for result in strategy.select_repos(
                    selector,
                    repo_exporter,
                    "test-org",
                    "Organization",
                    changed_since=RepositoryChange.pushed(pushed_since),
                )
            ]

        assert results == ["fresh", "unknown"]


@pytest.mark.asyncio
class TestMemoizedRepositorySelector:
    @staticmethod
    def _strategy(results: List[Any]) -> MagicMock:
        """A selector strategy that yields ``results`` and records each call."""
        strategy = MagicMock()

        def _select(*_: Any, **__: Any) -> AsyncIterator[Any]:
            async def _gen() -> AsyncIterator[Any]:
                for result in results:
                    yield result

            return _gen()

        strategy.select_repos = MagicMock(side_effect=_select)
        return strategy

    async def test_reuses_listing_including_empty_result(self) -> None:
        strategy = self._strategy([])
        memoized = MemoizedRepositorySelector(strategy)
        selector = RepositorySourceModel.parse_obj({})

        for _ in range(3):
            assert (
                await memoized.select_repos(
                    selector, MagicMock(), "org", "Organization"
                )
                == []
            )

        assert strategy.select_repos.call_count == 1

    async def test_lists_again_for_different_exclude_archived(self) -> None:
        strategy = self._strategy([("repo1", "main", {})])
        memoized = MemoizedRepositorySelector(strategy)

        for exclude_archived in (False, True, False):
            await memoized.select_repos(
                RepositorySourceModel.parse_obj({"excludeArchived": exclude_archived}),
                MagicMock(),
                "org",
                "Organization",
            )

        assert strategy.select_repos.call_count == 2

    async def test_explicit_repos_are_not_memoized(self) -> None:
        strategy = self._strategy([("explicit", "main", {})])
        memoized = MemoizedRepositorySelector(strategy)
        selector = RepositorySourceModel.parse_obj({"repos": [{"name": "explicit"}]})

        for _ in range(2):
            await memoized.select_repos(selector, MagicMock(), "org", "Organization")

        assert strategy.select_repos.call_count == 2

    async def test_forwards_pushed_since(self) -> None:
        pushed_since = datetime(2026, 10, 1, tzinfo=timezone.utc)
        strategy = self._strategy([])
        memoized = MemoizedRepositorySelector(strategy)

        await memoized.select_repos(
            RepositorySourceModel.parse_obj({}),
            MagicMock(),
            "org",
            "Organization",
            changed_since=RepositoryChange.pushed(pushed_since),
        )

        assert strategy.select_repos.call_args.args[-1] == RepositoryChange.pushed(
            pushed_since
        )
