from datetime import datetime, timezone
from typing import Any, AsyncIterator
from unittest.mock import MagicMock

import pytest

from github.core.options import ListRepositoryOptions
from github.helpers.models import RepoSearchParams
from github.helpers.repositories import iter_repositories

PUSHED_SINCE = datetime(2026, 6, 1, tzinfo=timezone.utc)
REPO_SEARCH = RepoSearchParams(query="topic:backend")


def _repo_exporter(
    listed: list[list[dict[str, Any]]], searched: list[list[dict[str, Any]]]
) -> MagicMock:
    """Exporter mock: `searched` batches for search calls, `listed` batches otherwise."""

    def _side_effect(options: ListRepositoryOptions) -> AsyncIterator[Any]:
        batches = searched if options.get("search_params") else listed

        async def _gen() -> AsyncIterator[Any]:
            for batch in batches:
                yield batch

        return _gen()

    exporter = MagicMock()
    exporter.get_paginated_resources = MagicMock(side_effect=_side_effect)
    return exporter


def _options(**kwargs: Any) -> ListRepositoryOptions:
    options = ListRepositoryOptions(
        organization="test-org", organization_type="Organization", type="all"
    )
    options.update(kwargs)  # type: ignore[typeddict-item]
    return options


async def _collect(
    exporter: MagicMock, options: ListRepositoryOptions
) -> list[list[dict[str, Any]]]:
    return [batch async for batch in iter_repositories(exporter, options)]


def _called_options(exporter: MagicMock) -> list[ListRepositoryOptions]:
    return [call.args[0] for call in exporter.get_paginated_resources.call_args_list]


@pytest.mark.asyncio
class TestIterRepositories:
    @pytest.mark.parametrize(
        "options",
        [
            _options(search_params=REPO_SEARCH),
            _options(pushed_since=PUSHED_SINCE),
            _options(),
        ],
    )
    async def test_passes_through_without_both_filters(
        self, options: ListRepositoryOptions
    ) -> None:
        exporter = _repo_exporter(listed=[[{"name": "a"}]], searched=[[{"name": "a"}]])

        assert await _collect(exporter, options) == [[{"name": "a"}]]
        assert _called_options(exporter) == [options]

    async def test_pushed_repos_come_from_list_and_search_only_filters(self) -> None:
        exporter = _repo_exporter(
            listed=[[{"name": "a"}, {"name": "b"}], [{"name": "c"}]],
            searched=[[{"name": "b"}, {"name": "c"}, {"name": "not-pushed"}]],
        )

        batches = await _collect(
            exporter,
            _options(
                search_params=REPO_SEARCH,
                pushed_since=PUSHED_SINCE,
                exclude_archived=True,
            ),
        )

        assert batches == [[{"name": "b"}], [{"name": "c"}]]
        pushed_options, search_options = _called_options(exporter)
        assert pushed_options["pushed_since"] == PUSHED_SINCE
        assert pushed_options["search_params"] is None
        assert pushed_options["exclude_archived"] is True
        assert search_options["search_params"] == REPO_SEARCH
        assert search_options["pushed_since"] is None
        assert search_options["exclude_archived"] is True

    async def test_skips_search_when_nothing_was_pushed(self) -> None:
        exporter = _repo_exporter(listed=[], searched=[[{"name": "a"}]])

        batches = await _collect(
            exporter, _options(search_params=REPO_SEARCH, pushed_since=PUSHED_SINCE)
        )

        assert batches == []
        assert len(_called_options(exporter)) == 1
