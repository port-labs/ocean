from typing import TypedDict

from pydantic import BaseModel


class PlaybooksExportOptions(BaseModel):
    include_enterprise: bool


class SessionsExportOptions(TypedDict):
    include_archived: bool
    created_after_days: int | None
    origins: list[str] | None
    only_managed_by_port: bool
