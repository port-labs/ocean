from typing import TypedDict


class ListCursorAnalyticsOptions(TypedDict):
    startDate: str
    endDate: str
    page: int
    pageSize: int


class ListCursorAdminOptions(TypedDict):
    startDate: int
    endDate: int
    page: int
    pageSize: int
