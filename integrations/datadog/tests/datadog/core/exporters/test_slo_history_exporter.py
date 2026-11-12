from datetime import datetime, timezone
from typing import Any, AsyncIterator, Iterator
from unittest.mock import AsyncMock, patch

import pytest

from datadog.client import DatadogClient
from datadog.core.exporters.slo_exporter import SloExporter
from datadog.core.exporters.slo_history_exporter import (
    ListSloHistoryOptions,
    SloHistoryExporter,
)

WEEK = 7 * 24 * 60 * 60
OPTIONS = ListSloHistoryOptions(timeframe=7, concurrency=2, period_of_time_in_months=1)
# Two closed weeks, then the current week, which ends in the future
WINDOWS = [(0, WEEK), (WEEK, 2 * WEEK), (2 * WEEK, 3 * WEEK)]


async def _list_slos(*_: Any, **__: Any) -> AsyncIterator[list[dict[str, Any]]]:
    yield [{"id": "a"}, {"id": "b"}]


async def _drain(histories: AsyncIterator[list[dict[str, Any]]]) -> None:
    async for _ in histories:
        pass


@pytest.fixture
def mock_get_history() -> Iterator[AsyncMock]:
    """Patch the time windows, the SLO listing and the history fetch."""
    with (
        patch(
            "datadog.core.exporters.slo_history_exporter.generate_time_windows_from_interval_days",
            return_value=WINDOWS,
        ),
        patch.object(SloExporter, "get_paginated_resources", new=_list_slos),
        patch.object(
            SloHistoryExporter, "_get_slo_history", new_callable=AsyncMock
        ) as mock_get_history,
    ):
        mock_get_history.return_value = {"slo": {"id": "any"}}
        yield mock_get_history


def _fetched(mock_get_history: AsyncMock) -> list[tuple[str, int, int]]:
    """The (slo id, from_ts, to_ts) of every history fetch, sorted."""
    fetched = []
    for awaited in mock_get_history.await_args_list:
        slo_id, _, from_ts, to_ts = awaited.args
        fetched.append((slo_id, from_ts, to_ts))
    return sorted(fetched)


def _expected(windows: list[tuple[int, int]]) -> list[tuple[str, int, int]]:
    expected = []
    for slo_id in ("a", "b"):
        for from_ts, to_ts in windows:
            expected.append((slo_id, from_ts, to_ts))
    return sorted(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "since_ts, expected_windows",
    [
        # Cursor inside the current week: only the current week
        (2 * WEEK + 10, [(2 * WEEK, 3 * WEEK)]),
        # A week closed since the cursor: that week and the current week
        (2 * WEEK - 10, [(WEEK, 2 * WEEK), (2 * WEEK, 3 * WEEK)]),
    ],
)
async def test_get_latest_histories_fetches_windows_ending_after_cursor(
    mock_datadog_client: DatadogClient,
    mock_get_history: AsyncMock,
    since_ts: int,
    expected_windows: list[tuple[int, int]],
) -> None:
    since = datetime.fromtimestamp(since_ts, tz=timezone.utc)

    await _drain(
        SloHistoryExporter(mock_datadog_client).get_latest_histories(
            OPTIONS, incremental_cursor=since
        )
    )

    assert _fetched(mock_get_history) == _expected(expected_windows)


@pytest.mark.asyncio
async def test_get_paginated_resources_fetches_every_window_for_all_slos(
    mock_datadog_client: DatadogClient,
    mock_get_history: AsyncMock,
) -> None:
    await _drain(
        SloHistoryExporter(mock_datadog_client).get_paginated_resources(OPTIONS)
    )

    assert _fetched(mock_get_history) == _expected(WINDOWS)
