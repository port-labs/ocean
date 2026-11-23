from enum import StrEnum
from typing import NotRequired, Optional, TypedDict


class AlertStatus(StrEnum):
    """Firing or resolved."""

    FIRING = "firing"
    RESOLVED = "resolved"


class IncidentStatusCategory(StrEnum):
    """Triage, active, post-incident, paused, closed, declined, canceled, or merged."""
    TRIAGE = "triage"
    LIVE = "live"
    LEARNING = "learning"
    PAUSED = "paused"
    CLOSED = "closed"
    DECLINED = "declined"
    CANCELED = "canceled"
    MERGED = "merged"


class IncidentOptions(TypedDict):
    days_back: int
    status_categories: NotRequired[Optional[list[IncidentStatusCategory]]]
    severities: NotRequired[Optional[list[str]]]
    include_test: NotRequired[bool]


class UserOptions(TypedDict):
    include_inactive: bool


class AlertOptions(TypedDict):
    days_back: int
    statuses: NotRequired[Optional[list[AlertStatus]]]
