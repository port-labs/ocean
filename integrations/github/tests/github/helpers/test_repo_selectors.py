from typing import Any, AsyncIterator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github.core.options import ListRepositoryOptions
from github.helpers.repo_selectors import AllRepositorySelector, ExactRepositorySelector
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
