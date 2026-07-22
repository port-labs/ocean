from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from port_ocean.version import __version__


class HealthResponse(BaseModel):
    """Structured payload for liveness/readiness probes and tooling."""

    status: Literal["healthy"] = "healthy"
    check: Literal["live", "ready"] = Field(
        ...,
        description="Whether this response is from the liveness or readiness endpoint.",
    )
    core_version: str = Field(
        default=__version__,
        description="Installed port-ocean (Ocean core) package version.",
    )


def create_health_router() -> APIRouter:
    router = APIRouter()

    @router.get(
        "/live",
        include_in_schema=False,
        response_model=HealthResponse,
    )
    async def health_live() -> HealthResponse:
        return HealthResponse(check="live")

    @router.get(
        "/ready",
        include_in_schema=False,
        response_model=HealthResponse,
    )
    async def health_ready() -> HealthResponse:
        return HealthResponse(check="ready")

    return router
