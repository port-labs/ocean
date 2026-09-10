from threading import Lock
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from port_ocean.version import __version__

_ready = False
_ready_lock = Lock()


def set_ready(ready: bool) -> None:
    with _ready_lock:
        global _ready
        _ready = ready


def is_ready() -> bool:
    with _ready_lock:
        return _ready


class HealthResponse(BaseModel):
    """Structured payload for liveness/readiness probes and tooling."""

    status: Literal["healthy", "not_ready"] = Field(
        default="healthy", description="The health of the service."
    )
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
    async def health_ready(response: Response) -> HealthResponse:
        if not is_ready():
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return HealthResponse(status="not_ready", check="ready")
        return HealthResponse(check="ready")

    return router
