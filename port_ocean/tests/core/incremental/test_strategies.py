"""Unit tests for incremental sync strategy utilities."""

from datetime import datetime, timezone

import pytest

from port_ocean.core.incremental.strategies import (
    ClientSideCutoffStrategy,
    ServerSideTimestampStrategy,
    paginate_with_strategy,
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

    def test_build_params_uses_value_prefix(self, cursor: datetime) -> None:
        strategy = ServerSideTimestampStrategy(
            param_key="created",
            date_format="%Y-%m-%dT%H:%M:%SZ",
            value_prefix=">=",
        )
        params = strategy.build_params(cursor)
        assert params == {"created": ">=2026-06-01T12:00:00Z"}

    def test_build_params_different_param_key(self, cursor: datetime) -> None:
        strategy = ServerSideTimestampStrategy(param_key="criteria.modifiedSince")
        params = strategy.build_params(cursor)
        assert "criteria.modifiedSince" in params

    def test_merge_params_spreads_into_base(self, cursor: datetime) -> None:
        strategy = ServerSideTimestampStrategy(param_key="since")
        assert strategy.merge_params({"state": "open"}, cursor) == {
            "state": "open",
            "since": "2026-06-01T12:00:00+00:00",
        }

    def test_merge_params_returns_base_when_no_cursor(self) -> None:
        strategy = ServerSideTimestampStrategy(param_key="since")
        base = {"state": "open"}
        assert strategy.merge_params(base, None) == base


class TestClientSideCutoffStrategy:
    @pytest.fixture
    def strategy(self) -> ClientSideCutoffStrategy:
        return ClientSideCutoffStrategy(
            stop_field="updated_at",
            query_params={"sort": "updated", "direction": "desc"},
        )

    def test_build_params_returns_query_params_when_cursor_given(
        self, strategy: ClientSideCutoffStrategy, cursor: datetime
    ) -> None:
        assert strategy.build_params(cursor) == {
            "sort": "updated",
            "direction": "desc",
        }

    def test_build_params_returns_empty_dict_when_no_cursor(
        self, strategy: ClientSideCutoffStrategy
    ) -> None:
        assert strategy.build_params(None) == {}

    def test_filter_page_returns_all_items_when_no_cursor(
        self, strategy: ClientSideCutoffStrategy
    ) -> None:
        page = [{"updated_at": "2020-01-01T00:00:00+00:00"}]
        assert strategy.filter_page(page, None) == page

    def test_filter_page_removes_items_predating_cursor(
        self, strategy: ClientSideCutoffStrategy, cursor: datetime
    ) -> None:
        page = [
            {"updated_at": "2026-06-15T12:00:00+00:00"},
            {"updated_at": "2026-05-01T12:00:00+00:00"},
        ]
        assert strategy.filter_page(page, cursor) == [
            {"updated_at": "2026-06-15T12:00:00+00:00"}
        ]

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

    def test_should_break_pagination_when_page_has_old_item(
        self, strategy: ClientSideCutoffStrategy, cursor: datetime
    ) -> None:
        page = [
            {"updated_at": "2026-06-15T12:00:00+00:00"},
            {"updated_at": "2026-05-01T12:00:00+00:00"},
        ]
        assert strategy.should_break_pagination(page, cursor) is True

    def test_should_break_pagination_false_when_no_cursor(
        self, strategy: ClientSideCutoffStrategy
    ) -> None:
        page = [{"updated_at": "2020-01-01T00:00:00+00:00"}]
        assert strategy.should_break_pagination(page, None) is False

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


class TestPaginateWithStrategy:
    async def test_paginate_with_strategy_passes_through_when_no_strategy(
        self,
    ) -> None:
        async def pages():
            yield [{"id": 1}]
            yield [{"id": 2}]

        batches = [
            batch
            async for batch in paginate_with_strategy(
                pages(), cursor=None, strategy=None
            )
        ]
        assert batches == [[{"id": 1}], [{"id": 2}]]

    async def test_paginate_with_strategy_stops_early_for_t2(
        self, cursor: datetime
    ) -> None:
        strategy = ClientSideCutoffStrategy(
            stop_field="updated_at",
            query_params={"sort": "updated", "direction": "desc"},
        )

        async def pages():
            yield [{"updated_at": "2026-06-15T12:00:00+00:00"}]
            yield [{"updated_at": "2026-05-01T12:00:00+00:00"}]

        batches = [
            batch
            async for batch in paginate_with_strategy(
                pages(), cursor=cursor, strategy=strategy
            )
        ]
        assert batches == [[{"updated_at": "2026-06-15T12:00:00+00:00"}]]

    async def test_paginate_with_strategy_passes_all_pages_for_t1(
        self, cursor: datetime
    ) -> None:
        strategy = ServerSideTimestampStrategy(param_key="since")

        async def pages():
            yield [{"id": 1}]
            yield [{"id": 2}]

        batches = [
            batch
            async for batch in paginate_with_strategy(
                pages(), cursor=cursor, strategy=strategy
            )
        ]
        assert batches == [[{"id": 1}], [{"id": 2}]]
