from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github.core.options import ListRepositoryOptions
from github.helpers.repo_selectors import (
    AllRepositorySelector,
    ExactRepositorySelector,
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


PUSHED_SINCE = datetime(2026, 6, 1, tzinfo=timezone.utc)


@pytest.mark.asyncio
class TestPushedSinceSelection:
    async def test_all_selector_passes_pushed_since_to_exporter(self) -> None:
        selector = RepositorySourceModel.parse_obj({})
        repo_exporter = MagicMock()
        repo_exporter.get_paginated_resources = _make_paginated_resources_mock(
            [[{"name": "repo1", "default_branch": "main"}]]
        )

        strategy = AllRepositorySelector("all")
        [
            result
            async for result in strategy.select_repos(
                selector, repo_exporter, "test-org", "Organization", PUSHED_SINCE
            )
        ]

        options = repo_exporter.get_paginated_resources.call_args.args[0]
        assert options["pushed_since"] == PUSHED_SINCE

    @pytest.mark.parametrize(
        "pushed_since, expected",
        [
            (PUSHED_SINCE, [("pushed", "release"), ("no-push-time", "main")]),
            (
                None,
                [("pushed", "release"), ("idle", "main"), ("no-push-time", "main")],
            ),
        ],
        ids=["incremental", "full-resync"],
    )
    async def test_exact_selector_skips_repos_not_pushed_since(
        self, pushed_since: datetime | None, expected: list[tuple[str, str]]
    ) -> None:
        selector = RepositorySourceModel.parse_obj(
            {
                "repos": [
                    {"name": "pushed", "branch": "release"},
                    {"name": "idle"},
                    {"name": "no-push-time"},
                ]
            }
        )
        repo_exporter = MagicMock()
        metadata = {
            "pushed": {
                "name": "pushed",
                "default_branch": "main",
                "pushed_at": "2026-06-02T00:00:00Z",
            },
            "idle": {
                "name": "idle",
                "default_branch": "main",
                "pushed_at": "2026-05-01T00:00:00Z",
            },
            "no-push-time": {"name": "no-push-time", "default_branch": "main"},
        }

        async def _get_metadata(client: Any, org: str, name: str) -> Dict[str, Any]:
            return metadata[name]

        with patch(
            "github.helpers.repo_selectors.get_repository_metadata",
            new=AsyncMock(side_effect=_get_metadata),
        ):
            strategy = ExactRepositorySelector()
            results = [
                (name, branch)
                async for name, branch, _ in strategy.select_repos(
                    selector, repo_exporter, "test-org", "Organization", pushed_since
                )
            ]

        assert results == expected
