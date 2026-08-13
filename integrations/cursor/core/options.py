from typing import TypedDict


class ListCursorAnalyticsOptions(TypedDict):
    startDate: str
    endDate: str


class ListCursorTeamSkillUsageOptions(ListCursorAnalyticsOptions, total=False):
    users: str


class ListCursorAdminOptions(TypedDict):
    startDate: int
    endDate: int
