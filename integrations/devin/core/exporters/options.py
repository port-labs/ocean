from typing import TypedDict


class ListPlaybooksOptions(TypedDict):
    include_enterprise: bool


class SessionsExportOptions(TypedDict):
    include_archived: bool
    created_after_days: int | None
    origins: list[str] | None
    only_managed_by_port: bool
