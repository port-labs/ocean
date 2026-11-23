"""Pydantic models for mock-server admin HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LoadScenarioRequest(BaseModel):
    """Route files to activate, relative to the mock fixture root."""

    model_config = ConfigDict(extra="forbid")

    routes: list[str] = Field(..., min_length=1)


class LoadScenarioResponse(BaseModel):
    route_ids: list[str]


class JournalEntry(BaseModel):
    method: str
    path: str
    query: dict[str, str]
    headers: dict[str, str]
    body: Any = None
    matched_route_id: str | None
    response_status: int


class JournalResponse(BaseModel):
    requests: list[JournalEntry]
    route_call_counts: dict[str, int]


class RouteUsage(BaseModel):
    route_id: str
    call_count: int


class ResetResponse(BaseModel):
    status: str = "reset"
