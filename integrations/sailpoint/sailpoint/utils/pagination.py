from typing import TypedDict, Protocol


class PaginatedResponse(TypedDict, total=False):
    # simple type to represent a paginated response
    items: list[dict]  # List of items in the current page
    total: int  # Total number of items across all pages


class PaginatorProtocol(Protocol):
    """
    Defines the public contract for any paginator implementation of ours

    Meaning any class that implements this protocol must provide the method
    `get_paginated_response` that takes a list of structured responses and returns a
    `PaginatedResponse`.

    This allows us to swap out pagination strategies easily in methods by composition e.g

    def fetch_items(paginator: PaginatorProtocol) -> PaginatedResponse:
        ...

    meaning we can use any paginator that implements the PaginatorProtocol e.g `LimitOffsetPagination` or `PageNumberPagination`
    and bothh will work seamlessly in our case; or even `CursorPagination` if we ever need it.
    """

    def get_paginated_response(self, data: list[dict]) -> PaginatedResponse: ...


class LimitOffsetPagination:
    SAILPOINT_MAX_LIMIT = 250
    SAILPOINT_DEFAULT_LIMIT = 100
    SAILPOINT_OFFSET_COUNT = 0

    def __init__(
        self,
        limit: int = SAILPOINT_DEFAULT_LIMIT,
        max_limit: int = SAILPOINT_MAX_LIMIT,
        offset: int = SAILPOINT_OFFSET_COUNT,
    ):
        self.limit = min(limit, max_limit)
        self.offset = offset

    def get_paginated_response(self, data: list[dict]) -> PaginatedResponse:
        return {}


class PageNumberPagination:
    # TODO: todo, you get the gist :wink: - implement this class
    pass
