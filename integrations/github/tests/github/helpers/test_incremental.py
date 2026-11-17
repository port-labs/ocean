from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from github.helpers.incremental import is_pushed_since

PUSHED_SINCE = datetime(2026, 11, 16, 15, 0, 0, tzinfo=timezone.utc)


class TestIsPushedSince:
    @pytest.mark.parametrize(
        ("repo", "expected"),
        [
            ({"pushed_at": "2026-11-16T15:30:00Z"}, True),
            ({"pushed_at": "2026-11-16T15:00:00Z"}, True),
            ({"pushed_at": "2026-11-16T14:59:59Z"}, False),
            ({"pushed_at": None}, False),
            ({"pushed_at": ""}, False),
            ({"name": "never-pushed"}, False),
        ],
    )
    def test_compares_pushed_at_with_cursor(
        self, repo: dict[str, Any], expected: bool
    ) -> None:
        assert is_pushed_since(repo, PUSHED_SINCE) is expected

    @pytest.mark.parametrize(
        "repo", [{"pushed_at": "2020-01-01T00:00:00Z"}, {"name": "never-pushed"}]
    )
    def test_no_cursor_keeps_every_repository(self, repo: dict[str, Any]) -> None:
        assert is_pushed_since(repo, None) is True

    def test_naive_cursor_is_treated_as_utc(self) -> None:
        naive_cursor = PUSHED_SINCE.replace(tzinfo=None)

        assert is_pushed_since({"pushed_at": "2026-11-16T15:00:00Z"}, naive_cursor)
        assert not is_pushed_since({"pushed_at": "2026-11-16T14:59:59Z"}, naive_cursor)

    def test_cursor_in_other_timezone_compares_same_instant(self) -> None:
        local_cursor = PUSHED_SINCE.astimezone(timezone(timedelta(hours=2)))

        assert is_pushed_since({"pushed_at": "2026-11-16T15:00:00Z"}, local_cursor)
        assert not is_pushed_since({"pushed_at": "2026-11-16T14:59:59Z"}, local_cursor)
