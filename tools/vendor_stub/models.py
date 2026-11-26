from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MockResponse(BaseModel):
    status: int = 200
    headers: dict[str, str] = Field(default_factory=dict)
    body: Any = {}


class MatchConditions(BaseModel):
    method: str | None = None
    path: str | None = None
    path_regex: str | None = None
    query: dict[str, Any] | None = None
    headers: dict[str, str] | None = None
    body_contains: str | None = None
    body_field: dict[str, Any] | None = None
    priority: int = 0


CONDITION_KEYS: tuple[str, ...] = (
    "method",
    "path",
    "path_regex",
    "query",
    "headers",
    "body_contains",
    "body_field",
)


class Registration(MatchConditions):
    """A stored mock route: match conditions plus the response to serve."""

    id: str | None = None
    response: MockResponse = Field(default_factory=MockResponse)
    times: int | list[MockResponse] | None = None

    def condition_count(self) -> int:
        return sum(1 for key in CONDITION_KEYS if getattr(self, key) is not None)


class PaginateRequest(MatchConditions):
    """Shared match conditions plus an ordered page sequence."""

    pages: list[MockResponse] = Field(min_length=1)
    priority: int = 10
