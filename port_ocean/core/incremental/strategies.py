"""Incremental sync strategy utilities.

Integration developers use these helpers inside their
``@ocean.on_incremental_resync`` handlers to translate a cursor timestamp
into the correct API parameters for their specific resource.

The cursor itself is available at runtime via::

    from port_ocean.core.incremental.cursor_context import active_incremental_cursor
    cursor: datetime | None = active_incremental_cursor()

Example — T1 (server-side filter)::

    strategy = ServerSideTimestampStrategy(param_key="since")

    @ocean.on_incremental_resync(Kind.ISSUE)
    async def incremental_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
        cursor = active_incremental_cursor()
        params = strategy.merge_params(base_params, cursor)
        async for batch in paginate_with_strategy(
            client.send_paginated_request(url, params),
            cursor=cursor,
            strategy=strategy,
        ):
            yield enrich(batch)

Example — T2 (client-side cutoff)::

    strategy = ClientSideCutoffStrategy(
        stop_field="updated_at",
        query_params={"sort": "updated", "direction": "desc"},
    )

    @ocean.on_incremental_resync(Kind.PULL_REQUEST)
    async def incremental_resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
        cursor = active_incremental_cursor()
        params = strategy.merge_params(base_params, cursor)
        async for batch in paginate_with_strategy(
            client.send_paginated_request(url, params),
            cursor=cursor,
            strategy=strategy,
        ):
            yield enrich(batch)
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any


class IncrementalStrategy(ABC):
    """Base class for incremental sync strategies.

    Each strategy encapsulates how a cursor timestamp is translated into an
    API call.  Subclasses implement either server-side filtering (T1) or
    client-side early-stop pagination (T2).
    """

    @abstractmethod
    def build_params(self, cursor: datetime | None) -> dict[str, Any]:
        """Return the API parameters derived from *cursor*.

        Returns an empty dict when *cursor* is ``None`` so callers can always
        spread the result into their request without extra branching.
        """
        ...

    def merge_params(
        self, base_params: dict[str, Any], cursor: datetime | None
    ) -> dict[str, Any]:
        """Merge :meth:`build_params` into *base_params*."""
        return {**base_params, **self.build_params(cursor)}

    def filter_page(
        self, page: list[dict[str, Any]], cursor: datetime | None
    ) -> list[dict[str, Any]]:
        """Return items to yield from *page* (T1 default: pass through)."""
        return page

    def should_break_pagination(
        self, page: list[dict[str, Any]], cursor: datetime | None
    ) -> bool:
        """Return ``True`` when paging should stop (T1 default: never)."""
        return False


class ServerSideTimestampStrategy(IncrementalStrategy):
    """T1 strategy: injects the cursor as a single URL query parameter.

    The server is responsible for filtering results; only items modified after
    *cursor* are returned.

    Args:
        param_key: The query-parameter name expected by the API
                   (e.g. ``"since"``, ``"minTime"``, ``"criteria.modifiedSince"``).
        date_format: Optional ``strftime`` format string.  Defaults to ISO 8601.
        value_prefix: Optional prefix prepended to the formatted value
                      (e.g. ``">="`` for GitHub workflow-run ``created`` param).
    """

    def __init__(
        self,
        param_key: str,
        date_format: str | None = None,
        value_prefix: str = "",
    ) -> None:
        self._param_key = param_key
        self._date_format = date_format
        self._value_prefix = value_prefix

    def build_params(self, cursor: datetime | None) -> dict[str, Any]:
        if cursor is None:
            return {}
        value = (
            cursor.strftime(self._date_format)
            if self._date_format
            else cursor.isoformat()
        )
        return {self._param_key: f"{self._value_prefix}{value}"}


class ClientSideCutoffStrategy(IncrementalStrategy):
    """T2 strategy: sorts results newest-first and stops when items predate the cursor.

    The server has no native time filter; the integration sorts results
    descending by a timestamp field and stops consuming pages once items
    become older than the cursor.

    Args:
        stop_field: The field name on each API response item that holds its
                    timestamp (e.g. ``"updated_at"``).
        query_params: Query parameters to request descending time order
                      (e.g. ``{"sort": "updated", "direction": "desc"}``).
                      Omit when the API already returns newest-first.
    """

    def __init__(
        self,
        *,
        stop_field: str,
        query_params: dict[str, Any] | None = None,
    ) -> None:
        self._stop_field = stop_field
        self._query_params = query_params or {}

    def build_params(self, cursor: datetime | None) -> dict[str, Any]:
        if cursor is None:
            return {}
        return dict(self._query_params)

    def filter_page(
        self, page: list[dict[str, Any]], cursor: datetime | None
    ) -> list[dict[str, Any]]:
        if cursor is None:
            return page
        return [item for item in page if not self.should_stop(item, cursor)]

    def should_break_pagination(
        self, page: list[dict[str, Any]], cursor: datetime | None
    ) -> bool:
        if cursor is None:
            return False
        return self.page_exhausted(page, cursor)

    def should_stop(self, item: dict[str, Any], cursor: datetime | None) -> bool:
        """Return ``True`` when *item* predates *cursor* and pagination should stop."""
        if cursor is None:
            return False
        raw = item.get(self._stop_field)
        if not raw:
            return False
        item_time = datetime.fromisoformat(str(raw))
        return item_time < cursor

    def page_exhausted(
        self, page: list[dict[str, Any]], cursor: datetime | None
    ) -> bool:
        """Return ``True`` when at least one item in *page* predates *cursor*.

        Use this after filtering a page to decide whether to request the next
        one: if any item on the current page is already older than the cursor,
        all subsequent pages will be older too.
        """
        return any(self.should_stop(item, cursor) for item in page)


async def paginate_with_strategy(
    pages: AsyncIterator[list[dict[str, Any]]],
    *,
    cursor: datetime | None,
    strategy: IncrementalStrategy | None,
) -> AsyncIterator[list[dict[str, Any]]]:
    """Walk paginated API pages applying strategy filter and early-stop."""
    if strategy is None:
        async for page in pages:
            yield page
        return

    async for page in pages:
        batch = strategy.filter_page(page, cursor)
        if batch:
            yield batch
        if strategy.should_break_pagination(page, cursor):
            break
