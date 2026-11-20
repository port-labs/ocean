from typing import NotRequired, Optional, TypedDict


class IncidentOptions(TypedDict):
    days_back: int
    status_categories: NotRequired[Optional[list[str]]]
    severities: NotRequired[Optional[list[str]]]
    include_test: NotRequired[bool]


class UserOptions(TypedDict):
    include_inactive: bool


class AlertOptions(TypedDict):
    days_back: int
    statuses: NotRequired[Optional[list[str]]]
