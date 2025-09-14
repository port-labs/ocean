from typing import TypedDict, Protocol, Any, Optional


class PaginatedResponse(TypedDict, total=False):
    count: int
    next: Optional[str]
    previous: Optional[str]
    results: list[dict]


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

    def get_paginated_response(
        self, data: list[dict], total: Optional[int] = None
    ) -> PaginatedResponse: ...
    def get_query_params(self) -> dict[str, Any]: ...
    def advance(self) -> None: ...
    def has_more(self, last_page_count: int) -> bool: ...


class LimitOffsetPagination:
    """
    Limit-Offset based pagination strategy.

    Inspiration:
    - https://www.django-rest-framework.org/api-guide/pagination/#limitoffsetpagination

    Don't judge me i just like that framework better :P
    """

    SAILPOINT_MAX_LIMIT = 250
    SAILPOINT_DEFAULT_LIMIT = 100
    SAILPOINT_OFFSET_COUNT = 0

    def __init__(
        self,
        limit: int = SAILPOINT_DEFAULT_LIMIT,
        offset: int = SAILPOINT_OFFSET_COUNT,
        request_total: bool = False,  # always ask SailPoint for X-Total-Count
        base_url: str = "",
    ):
        self.limit = min(limit, self.SAILPOINT_MAX_LIMIT)
        self.offset = offset
        self.request_total = request_total
        self.total: Optional[int] = None
        self.base_url = base_url.rstrip("/")

    def get_paginated_response(
        self, data: list[dict], total: Optional[int] = None, base_url: str = ""
    ) -> PaginatedResponse:
        if total is not None:
            self.total = total

        next_url = None
        previous_url = None

        if self.total is not None:
            if self.offset + self.limit < self.total:
                next_url = f"{self.base_url}?limit={self.limit}&offset={self.offset + self.limit}"
            if self.offset > 0:
                prev_offset = max(0, self.offset - self.limit)
                previous_url = (
                    f"{self.base_url}?limit={self.limit}&offset={prev_offset}"
                )

        return {
            "count": self.total if self.total is not None else len(data),
            "next": next_url,
            "previous": previous_url,
            "results": data,
        }

    def get_query_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": self.limit, "offset": self.offset}

        if self.request_total:
            params["count"] = "true"
        return params

    def advance(self) -> None:
        self.offset += self.limit

    def has_more(self, last_page_count: int) -> bool:
        if self.request_total and self.total is not None:
            return self.offset < self.total
        return last_page_count == self.limit


class PageNumberPagination:
    # TODO: todo, you get the gist :wink: - implement this class
    pass
