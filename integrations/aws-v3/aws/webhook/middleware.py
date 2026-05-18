"""Path-scoped bearer-token middleware for AWS-V3 live events.

The Ocean `LiveEventsProcessorManager` enqueues requests and returns HTTP
200 before any per-processor `authenticate()` runs (see
`port_ocean/core/handlers/webhook/processor_manager.py:339-356`). EventBridge
relies on non-2xx responses to retry and DLQ failed deliveries — without a
401 at the edge, a misconfigured bearer in the customer's CloudFormation
stack would silently drop every event.

This middleware closes that gap by validating `Authorization` against the
integration's `webhook_secret` for POSTs to the live-events path, returning
HTTP 401 before the framework handler runs. Per-processor `authenticate()`
remains as defense-in-depth.
"""

from __future__ import annotations

import hmac
from typing import Awaitable, Callable

from fastapi import Request, Response, status
from loguru import logger

from port_ocean.context.ocean import ocean


_BEARER_PREFIX = "bearer "


def _extract_bearer_token(header_value: str | None) -> str | None:
    if not header_value:
        return None
    if not header_value.lower().startswith(_BEARER_PREFIX):
        return None
    return header_value[len(_BEARER_PREFIX) :].strip() or None


def _log_live_events_auth_rejection(
    request: Request,
    *,
    reason_code: str,
    provided_token: str | None,
    configured_secret: str | None,
) -> None:
    """Log **safe** diagnostics when rejecting a request (no secrets / tokens).

    Lengths and booleans are enough to spot the usual failures: missing
    `webhook_secret` in config, ``Bearer `` not sent by EventBridge, trailing
    ``\r`` from CRLF (length mismatch), or a different token than Secrets
    Manager vs ``.env``.
    """
    auth_raw = request.headers.get("Authorization") or request.headers.get(
        "authorization"
    )
    bits: list[str] = [
        f"reason={reason_code}",
        f"path={request.url.path}",
    ]
    client = request.client
    if client is not None and client.host:
        bits.append(f"client_host={client.host}")
    ua = request.headers.get("user-agent") or request.headers.get("User-Agent")
    if ua:
        bits.append(f"user_agent={ua[:200]}")

    bits.append(f"authorization_header_present={auth_raw is not None}")
    if auth_raw is not None:
        bits.append(f"authorization_header_length={len(auth_raw)}")
        bits.append(
            "authorization_has_bearer_prefix="
            f"{auth_raw.lower().startswith(_BEARER_PREFIX)}"
        )

    if provided_token is not None:
        bits.append(f"parsed_bearer_token_length={len(provided_token)}")

    if configured_secret:
        cfg = str(configured_secret)
        bits.append(f"configured_webhook_secret_length={len(cfg)}")
        if provided_token is not None:
            bits.append(
                "token_and_config_lengths_match=" f"{len(provided_token) == len(cfg)}"
            )
    else:
        bits.append("configured_webhook_secret_present=false")

    logger.warning(
        "Live-events webhook rejected — {}",
        ", ".join(bits),
    )


def _is_live_events_request(request: Request, live_events_path: str) -> bool:
    """Match POSTs whose path equals (or ends with) the live-events path.

    We accept both an exact match and a suffix match because the framework
    mounts the integration router under `route_prefix + /integration`, and
    `route_prefix` is read from runtime config that may not be available
    when this middleware is being registered at import time.
    """
    if request.method != "POST":
        return False
    path = request.url.path
    return path == live_events_path or path.endswith(live_events_path)


def build_live_events_auth_middleware(
    live_events_path: str,
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    """Return a FastAPI middleware that enforces bearer auth on the live-events path."""

    async def live_events_auth_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not _is_live_events_request(request, live_events_path):
            return await call_next(request)

        configured_secret = ocean.integration_config.get("webhook_secret")
        if not configured_secret:
            probe = _extract_bearer_token(request.headers.get("Authorization"))
            _log_live_events_auth_rejection(
                request,
                reason_code="no_webhook_secret_configured",
                provided_token=probe,
                configured_secret=None,
            )
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content="Unauthorized",
            )

        provided_token = _extract_bearer_token(request.headers.get("Authorization"))
        if not provided_token:
            _log_live_events_auth_rejection(
                request,
                reason_code="missing_or_malformed_authorization",
                provided_token=None,
                configured_secret=configured_secret,
            )
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content="Unauthorized",
            )

        if not hmac.compare_digest(provided_token, str(configured_secret)):
            _log_live_events_auth_rejection(
                request,
                reason_code="bearer_token_mismatch",
                provided_token=provided_token,
                configured_secret=configured_secret,
            )
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content="Unauthorized",
            )

        return await call_next(request)

    return live_events_auth_middleware


def register_live_events_auth_middleware(live_events_path: str) -> None:
    """Attach the bearer-auth middleware to the FastAPI app at import time."""
    ocean.app.fast_api_app.middleware("http")(
        build_live_events_auth_middleware(live_events_path)
    )
