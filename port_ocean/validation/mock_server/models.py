"""Pydantic models for mock-server route YAML files (design §5.2)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class MockRouteRequest(BaseModel):
    """Match criteria for an incoming request.

    ``method`` and ``path`` are required. ``query``, ``headers`` and ``body`` are
    optional subset matchers: listed keys must match; unlisted keys are ignored.
    ``path`` may include ``{param}`` templates.
    """

    model_config = ConfigDict(extra="forbid")

    method: HttpMethod
    path: str = Field(..., min_length=1)
    query: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    body: Any | None = None

    @field_validator("method", mode="before")
    @classmethod
    def _normalize_method(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.upper()
        return value

    @field_validator("query", "headers", mode="before")
    @classmethod
    def _stringify_mapping_values(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, dict):
            return value
        return {
            str(key): "" if item is None else str(item) for key, item in value.items()
        }


class MockRouteResponse(BaseModel):
    """A single HTTP response returned by a matched route."""

    model_config = ConfigDict(extra="forbid")

    status: int = Field(..., ge=100, le=599)
    headers: dict[str, str] | None = None
    body: Any | None = None
    body_file: str | None = None
    fallback_body: Any | None = None
    response_model: str | None = Field(
        default=None,
        description="Dotted reference to a VendorModel, e.g. 'team.TeamListResponse'.",
    )

    @field_validator("headers", mode="before")
    @classmethod
    def _stringify_header_values(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, dict):
            return value
        return {
            str(key): "" if item is None else str(item) for key, item in value.items()
        }

    @field_validator("body_file", "response_model", mode="before")
    @classmethod
    def _strip_optional_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class MockRoute(BaseModel):
    """One mock route: match criteria plus either a single response or a sequence."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    request: MockRouteRequest
    response: MockRouteResponse | None = None
    sequence: list[MockRouteResponse] | None = None
    verified: bool = True

    @model_validator(mode="after")
    def _require_response_or_sequence(self) -> MockRoute:
        has_response = self.response is not None
        has_sequence = self.sequence is not None and len(self.sequence) > 0
        if has_response == has_sequence:
            raise ValueError(
                f"Route '{self.id}' must define exactly one of 'response' or "
                f"'sequence' (a non-empty list)"
            )
        return self


class MockRouteFile(BaseModel):
    """Top-level contents of a ``mock/routes/*.yaml`` file."""

    model_config = ConfigDict(extra="forbid")

    routes: list[MockRoute] = Field(default_factory=list)
