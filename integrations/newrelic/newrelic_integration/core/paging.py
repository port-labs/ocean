from typing import (
    Any,
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Coroutine,
    Iterable,
    Optional,
    Tuple,
    TypeVar,
)
import httpx
from newrelic_integration.core.utils import render_query, send_graph_api_request

ReturnType = TypeVar("ReturnType")
ResponseType = TypeVar("ResponseType")

__all__ = ["AsyncPageIterator", "AsyncItemPaged"]


class AsyncList(AsyncIterator[ReturnType]):
    def __init__(self, iterable: Iterable[ReturnType]) -> None:
        """Change an iterable into a fake async iterator.

        Could be useful to fill the async iterator contract when you get a list.

        :param iterable: A sync iterable of T
        """
        # Technically, if it's a real iterator, I don't need "iter"
        # but that will cover iterable and list as well with no troubles created.
        self._iterator = iter(iterable)

    async def __anext__(self) -> ReturnType:
        try:
            return next(self._iterator)
        except StopIteration as err:
            raise StopAsyncIteration() from err


class AsyncPageIterator(AsyncIterator[AsyncIterator[ReturnType]]):
    def __init__(
        self,
        get_next: Callable[[Optional[str]], Awaitable[ResponseType]],
        extract_data: Callable[
            [ResponseType], Awaitable[Tuple[str, AsyncIterator[ReturnType]]]
        ],
        next_cursor: Optional[str] = None,
    ) -> None:
        """Return an async iterator of pages.

        :param get_next: Callable that take the continuation token and return a HTTP response
        :param extract_data: Callable that take an HTTP response and return a tuple continuation token,
         list of ReturnType
        :param str next_cursor: The cursor token needed to get the next page
        """
        self._get_next = get_next
        self._extract_data = extract_data
        self.next_cursor = next_cursor
        self._did_a_call_already = False
        self._response: Optional[ResponseType] = None
        self._current_page: Optional[AsyncIterator[ReturnType]] = None

    async def __anext__(self) -> AsyncIterator[ReturnType]:
        if self.next_cursor is None and self._did_a_call_already:
            raise StopAsyncIteration("End of paging")

        self._response = await self._get_next(self.next_cursor)

        self._did_a_call_already = True

        self.next_cursor, current_page = await self._extract_data(self._response)
        self._current_page = AsyncList(current_page)  # type: ignore

        return self._current_page


class AsyncItemPaged(AsyncIterator[ReturnType]):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Return an async iterator of items.
        args and kwargs will be passed to the AsyncPageIterator constructor directly,
        except page_iterator_class
        """
        self._args = args
        self._kwargs = kwargs
        self._page_iterator: Optional[AsyncIterator[AsyncIterator[ReturnType]]] = None
        self._page: Optional[AsyncIterator[ReturnType]] = None
        self._page_iterator_class = self._kwargs.pop(
            "page_iterator_class", AsyncPageIterator
        )

    def by_page(
        self,
    ) -> AsyncIterator[AsyncIterator[ReturnType]]:
        """Get an async iterator of pages of objects, instead of an async iterator of objects.
        :returns: An async iterator of pages (themselves async iterator of objects)
        :rtype: AsyncIterator[AsyncIterator[ReturnType]]
        """
        return self._page_iterator_class(*self._args, **self._kwargs)

    async def __anext__(self) -> ReturnType:
        """
        :returns: The next item
        :rtype: ReturnType
        :raises StopAsyncIteration: When there is no more item
        """
        if self._page_iterator is None:
            self._page_iterator = self.by_page()
            return await self.__anext__()
        if self._page is None:
            # Let it raise StopAsyncIteration
            self._page = await self._page_iterator.__anext__()
            return await self.__anext__()
        try:
            return await self._page.__anext__()
        except StopAsyncIteration:
            self._page = None
            return await self.__anext__()


def send_paginated_graph_api_request(
    http_client: httpx.AsyncClient,
    query_template: str,
    request_type: str,
    extract_data: Callable[
        [dict[Any, Any]], Coroutine[Any, Any, tuple[str | None, list[dict[Any, Any]]]]
    ],
    **kwargs: Any,
) -> AsyncIterable[dict[str, Any]]:
    """Send a paginated GraphQL request.
    :param http_client: The http client to use
    :param query_template: The GraphQL query template
    :param request_type: The type of the request, used for logging
    :param extract_data: A coroutine that take a GraphQL response and return a tuple of
        continuation token and list of ReturnType
    :param kwargs: The kwargs to pass to the query template
    :returns: An async iterator of ReturnType
    """

    async def prepare_query(next_cursor: str | None) -> str:
        if not next_cursor:
            query = await render_query(query_template, next_cursor_request="", **kwargs)
        else:
            query = await render_query(
                query_template,
                next_cursor_request=f'(cursor: "{next_cursor}")',
                **kwargs,
            )
        return query

    async def get_next(next_cursor: str | None) -> AsyncIterator[dict[str, Any]]:
        query = await prepare_query(next_cursor)
        return await send_graph_api_request(
            async_client=http_client,
            query=query,
            request_type=request_type,
            next_cursor=next_cursor,
        )

    return AsyncItemPaged(get_next, extract_data)
