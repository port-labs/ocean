"""Unit tests for incremental cursor context."""

from datetime import datetime, timezone

from port_ocean.core.incremental.cursor_context import (
    active_incremental_cursor,
    with_active_incremental_cursor,
)


class TestIncrementalCursorContext:
    def test_default_is_none(self) -> None:
        assert active_incremental_cursor() is None

    def test_with_active_cursor_sets_and_clears(self) -> None:
        cursor = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert active_incremental_cursor() is None

        with with_active_incremental_cursor(cursor):
            assert active_incremental_cursor() == cursor

        assert active_incremental_cursor() is None

    def test_nested_scopes_restore_outer_cursor(self) -> None:
        outer = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        inner = datetime(2026, 6, 1, 11, 0, 0, tzinfo=timezone.utc)

        with with_active_incremental_cursor(outer):
            assert active_incremental_cursor() == outer
            with with_active_incremental_cursor(inner):
                assert active_incremental_cursor() == inner
            assert active_incremental_cursor() == outer

        assert active_incremental_cursor() is None
