from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SessionPullRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    pr_url: str
    pr_state: str | None = None


class SessionResponse(BaseModel):
    """Typed view of the fields this integration reads off a Devin session.

    `extra="allow"` keeps every other field, so `raw()` hands the catalog the
    full API payload rather than only what is modelled here.
    """

    model_config = ConfigDict(extra="allow")

    session_id: str
    url: str
    status: str
    status_detail: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: int
    updated_at: int
    acus_consumed: float = 0
    on_demand_usage: float | None = None
    pull_requests: list[SessionPullRequest] = Field(default_factory=list)
    structured_output: dict[str, Any] | None = None
    is_archived: bool = False

    def raw(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SessionMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_id: str
    source: str
    message: str
    created_at: int
