"""Unit tests for incremental sync strategy utilities."""

from datetime import datetime, timezone

import pytest

from port_ocean.core.incremental.strategies import (
    ClientSideCutoffStrategy,
    ServerSideTimestampStrategy,
)


@pytest.fixture
def cursor() -> datetime:
    return datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


class TestServerSideTimestampStrategy:
    def test_build_params_returns_iso_param_when_cursor_given(
        self, cursor: datetime
    ) -> None:
        strategy = ServerSideTimestampStrategy(param_key="since")
        params = strategy.build_params(cursor)
        assert params == {"since": "2026-06-01T12:00:00+00:00"}

    def test_build_params_returns_empty_dict_when_no_cursor(self) -> None:
        strategy = ServerSideTimestampStrategy(param_key="since")
        assert strategy.build_params(None) == {}

    def test_build_params_uses_custom_date_format(self, cursor: datetime) -> None:
        strategy = ServerSideTimestampStrategy(
            param_key="minTime", date_format="%Y-%m-%dT%H:%M:%SZ"
        )
        params = strategy.build_params(cursor)
        assert params == {"minTime": "2026-06-01T12:00:00Z"}

    def test_build_params_different_param_key(self, cursor: datetime) -> None:
        strategy = ServerSideTimestampStrategy(param_key="criteria.modifiedSince")
        params = strategy.build_params(cursor)
        assert "criteria.modifiedSince" in params

    def test_build_params_returns_empty_dict_with_custom_format_and_no_cursor(
        self,
    ) -> None:
        strategy = ServerSideTimestampStrategy(
            param_key="minTime", date_format="%Y-%m-%dT%H:%M:%SZ"
        )
        assert strategy.build_params(None) == {}


class TestClientSideCutoffStrategy:
    @pytest.fixture
    def strategy(self) -> ClientSideCutoffStrategy:
        return ClientSideCutoffStrategy(
            sort_param="sort=updated&direction=desc",
            stop_field="updated_at",
        )

    def test_build_params_returns_sort_param_regardless_of_cursor(
        self, strategy: ClientSideCutoffStrategy, cursor: datetime
    ) -> None:
        assert strategy.build_params(cursor) == {"sort=updated&direction=desc": True}

    def test_build_params_returns_sort_param_when_no_cursor(
        self, strategy: ClientSideCutoffStrategy
    ) -> None:
        assert strategy.build_params(None) == {"sort=updated&direction=desc": True}

    def test_should_stop_returns_true_when_item_predates_cursor(
        self, strategy: ClientSideCutoffStrategy, cursor: datetime
    ) -> None:
        old_item = {"updated_at": "2026-05-01T12:00:00+00:00"}
        assert strategy.should_stop(old_item, cursor) is True

    def test_should_stop_returns_false_when_item_is_newer_than_cursor(
        self, strategy: ClientSideCutoffStrategy, cursor: datetime
    ) -> None:
        new_item = {"updated_at": "2026-06-15T12:00:00+00:00"}
        assert strategy.should_stop(new_item, cursor) is False

    def test_should_stop_returns_false_when_no_cursor(
        self, strategy: ClientSideCutoffStrategy
    ) -> None:
        old_item = {"updated_at": "2020-01-01T00:00:00+00:00"}
        assert strategy.should_stop(old_item, None) is False

    def test_should_stop_returns_false_when_item_missing_stop_field(
        self, strategy: ClientSideCutoffStrategy, cursor: datetime
    ) -> None:
        assert strategy.should_stop({}, cursor) is False

    def test_page_exhausted_returns_true_when_any_item_predates_cursor(
        self, strategy: ClientSideCutoffStrategy, cursor: datetime
    ) -> None:
        page = [
            {"updated_at": "2026-06-15T12:00:00+00:00"},
            {"updated_at": "2026-05-01T12:00:00+00:00"},
        ]
        assert strategy.page_exhausted(page, cursor) is True

    def test_page_exhausted_returns_false_when_all_items_are_newer(
        self, strategy: ClientSideCutoffStrategy, cursor: datetime
    ) -> None:
        page = [
            {"updated_at": "2026-06-15T12:00:00+00:00"},
            {"updated_at": "2026-06-10T00:00:00+00:00"},
        ]
        assert strategy.page_exhausted(page, cursor) is False

    def test_page_exhausted_returns_false_for_empty_page(
        self, strategy: ClientSideCutoffStrategy, cursor: datetime
    ) -> None:
        assert strategy.page_exhausted([], cursor) is False
