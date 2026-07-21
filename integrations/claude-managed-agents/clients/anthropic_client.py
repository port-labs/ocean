from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterable, Awaitable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

import httpx
from anthropic import AsyncAnthropic
from anthropic.types.beta import UnwrapWebhookEvent
from anthropic.types.beta.sessions.beta_managed_agents_session_event import (
    BetaManagedAgentsSessionEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_user_message_event import (
    BetaManagedAgentsUserMessageEvent,
)
from loguru import logger
from pydantic import BaseModel
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryConfig

from clients.exceptions import (
    UnexpectedApiResponseError,
    WebhookSigningSecretNotConfiguredError,
)

DEFAULT_PAGE_SIZE = 50

_RATE_LIMIT_LIMIT_HEADER = "anthropic-ratelimit-requests-limit"
_RATE_LIMIT_REMAINING_HEADER = "anthropic-ratelimit-requests-remaining"
_RATE_LIMIT_RESET_HEADER = "anthropic-ratelimit-requests-reset"
_WORKSPACE_ID_HEADER = "anthropic-workspace-id"

RateLimitPool = Literal["create", "read"]


@dataclass(frozen=True)
class RateLimitInfo:
    """Snapshot of a Managed Agents RPM limit.

    Create endpoints (agents/sessions/environments create) and read endpoints
    (list/retrieve) draw from two separate pools, both reported via the same
    ``anthropic-ratelimit-requests-*`` headers; see `AnthropicClient._on_response`.
    """

    limit: int
    remaining: int
    reset: datetime

    @property
    def seconds_until_reset(self) -> float:
        return max(0.0, (self.reset - datetime.now(timezone.utc)).total_seconds())


class _ToDictModel(Protocol):
    """Structural type for the SDK models a `list(...)` paginator yields: the
    only capability `AnthropicClient.paginate` needs from each page item."""

    def to_dict(
        self, *, mode: Literal["json", "python"] = ...
    ) -> dict[str, object]: ...


class _SessionEventsListParams(BaseModel):
    """`sessions.events.list` filters; unset fields are omitted from the request
    rather than sent as ``null`` (the SDK distinguishes the two)."""

    types: Sequence[str] | None = None
    order: Literal["asc", "desc"] | None = None
    created_at_gt: datetime | None = None
    created_at_gte: datetime | None = None
    created_at_lt: datetime | None = None
    created_at_lte: datetime | None = None
    limit: int | None = None


class AnthropicClient:
    def __init__(
        self,
        api_host: str,
        api_key: str,
        console_host: str,
        webhook_signing_secret: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        anthropic_version: str | None = None,
    ) -> None:
        self._console_host = console_host.rstrip("/")
        self._webhook_signing_secret = webhook_signing_secret
        self._page_size = page_size
        self._create_rate_limit_info: RateLimitInfo | None = None
        self._read_rate_limit_info: RateLimitInfo | None = None
        self._create_rate_limit_lock = asyncio.Lock()
        self._read_rate_limit_lock = asyncio.Lock()
        self._workspace_id: str | None = None
        self._client = AsyncAnthropic(
            api_key=api_key,
            base_url=api_host.rstrip("/"),
            default_headers=(
                {"anthropic-version": anthropic_version} if anthropic_version else None
            ),
            # A dedicated OceanAsyncClient gets us SaaS IP-blocking and consistent
            # SSL verification. Ocean's own retry layer is disabled (max_attempts=0)
            # since the Anthropic SDK already retries internally. The request/
            # response hooks below capture rate limit headers and proactively
            # pace requests for both the create- and read-endpoint pools, on
            # every call the client makes (resync, actions, and webhooks alike).
            http_client=OceanAsyncClient(
                timeout=ocean.config.client_timeout,
                retry_config=RetryConfig(max_attempts=0),
                event_hooks={
                    "request": [self._on_request],
                    "response": [self._on_response],
                },
            ),
        )

    def _rate_limit_lock(self, pool: RateLimitPool) -> asyncio.Lock:
        return (
            self._create_rate_limit_lock
            if pool == "create"
            else self._read_rate_limit_lock
        )

    def _get_rate_limit_info(self, pool: RateLimitPool) -> RateLimitInfo | None:
        return (
            self._create_rate_limit_info
            if pool == "create"
            else self._read_rate_limit_info
        )

    def _set_rate_limit_info(
        self, pool: RateLimitPool, info: RateLimitInfo | None
    ) -> None:
        if pool == "create":
            self._create_rate_limit_info = info
        else:
            self._read_rate_limit_info = info

    @staticmethod
    def _pool_for_method(method: str) -> RateLimitPool:
        """Managed Agents create endpoints (agents/sessions/environments
        create) are the only non-GET calls this client makes; everything else
        (list/retrieve) is a read endpoint."""
        return "read" if method == "GET" else "create"

    def _parse_rate_limit_headers(self, headers: httpx.Headers) -> RateLimitInfo | None:
        limit = headers.get(_RATE_LIMIT_LIMIT_HEADER)
        remaining = headers.get(_RATE_LIMIT_REMAINING_HEADER)
        reset = headers.get(_RATE_LIMIT_RESET_HEADER)
        if limit is None or remaining is None or reset is None:
            return None
        try:
            return RateLimitInfo(
                limit=int(limit),
                remaining=int(remaining),
                reset=datetime.fromisoformat(reset.replace("Z", "+00:00")),
            )
        except (TypeError, ValueError) as error:
            logger.warning(
                f"Failed to parse Managed Agents rate limit headers: {error}"
            )
            return None

    async def _on_request(self, request: httpx.Request) -> None:
        """Proactive safety net: pauses before a request only once a pool is
        known (from a prior response) to be fully exhausted, then lets the
        next response refresh it. Otherwise optimistically pre-decrements the
        cached count so a burst of concurrent requests can't all see the same
        stale `remaining` value and overshoot it before any response returns.
        """
        pool = self._pool_for_method(request.method)
        async with self._rate_limit_lock(pool):
            info = self._get_rate_limit_info(pool)
            if info is None:
                return
            if info.remaining <= 0:
                wait_seconds = info.seconds_until_reset
                if wait_seconds > 0:
                    logger.debug(
                        f"Managed Agents {pool}-endpoints rate limit exhausted; "
                        f"waiting {wait_seconds:.1f}s before {request.method} "
                        f"{request.url.path}"
                    )
                    await asyncio.sleep(wait_seconds)
                self._set_rate_limit_info(pool, None)
            else:
                self._set_rate_limit_info(
                    pool, replace(info, remaining=info.remaining - 1)
                )

    async def _on_response(self, response: httpx.Response) -> None:
        workspace_id = response.headers.get(_WORKSPACE_ID_HEADER)
        if workspace_id:
            self._workspace_id = workspace_id

        info = self._parse_rate_limit_headers(response.headers)
        if info is None:
            return
        pool = self._pool_for_method(response.request.method)
        async with self._rate_limit_lock(pool):
            self._set_rate_limit_info(pool, info)

    def get_create_rate_limit_status(self) -> RateLimitInfo | None:
        return self._create_rate_limit_info

    def get_read_rate_limit_status(self) -> RateLimitInfo | None:
        return self._read_rate_limit_info

    def get_workspace_id(self) -> str | None:
        return self._workspace_id

    def get_console_host(self) -> str:
        return self._console_host

    @property
    def beta(self) -> Any:
        """Direct access to the SDK's Managed Agents namespace, for exporters to
        call the resource they're responsible for. Rate limiting and pacing are
        applied transparently at the transport layer (see `_on_request`/
        `_on_response`), so callers don't need to consider it here."""
        return self._client.beta

    async def paginate(
        self, list_call: Awaitable[AsyncIterable[_ToDictModel]]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Await an SDK `list(...)` call and yield its records in fixed-size,
        serialized batches."""
        paginator = await list_call
        batch: list[dict[str, Any]] = []
        async for item in paginator:
            batch.append(item.to_dict(mode="json"))
            if len(batch) >= self._page_size:
                yield batch
                batch = []
        if batch:
            yield batch

    async def get_session(self, session_id: str) -> dict[str, Any]:
        session = await self._client.beta.sessions.retrieve(session_id)
        return session.to_dict(mode="json")

    async def get_session_events(
        self,
        session_id: str,
        *,
        types: Sequence[str] | None = None,
        order: Literal["asc", "desc"] | None = None,
        created_at_gt: datetime | None = None,
        created_at_gte: datetime | None = None,
        created_at_lt: datetime | None = None,
        created_at_lte: datetime | None = None,
        limit: int | None = None,
    ) -> AsyncGenerator[list[BetaManagedAgentsSessionEvent], None]:
        list_kwargs = _SessionEventsListParams(
            types=types,
            order=order,
            created_at_gt=created_at_gt,
            created_at_gte=created_at_gte,
            created_at_lt=created_at_lt,
            created_at_lte=created_at_lte,
            limit=limit,
        ).model_dump(exclude_none=True)

        paginator = await self._client.beta.sessions.events.list(
            session_id, **list_kwargs
        )
        batch: list[BetaManagedAgentsSessionEvent] = []
        async for event in paginator:
            batch.append(event)
            if len(batch) >= self._page_size:
                yield batch
                batch = []
        if batch:
            yield batch

    async def get_vault(self, vault_id: str) -> dict[str, Any]:
        vault = await self._client.beta.vaults.retrieve(vault_id)
        return vault.to_dict(mode="json")

    async def create_agent(
        self,
        name: str,
        model: str,
        system: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            k: v for k, v in (extra or {}).items() if v is not None
        }
        payload["name"] = name
        payload["model"] = model
        if system is not None:
            payload["system"] = system

        logger.info(f"Creating Claude agent '{name}' with model '{model}'")
        agent = await self._client.beta.agents.create(**payload)
        return agent.to_dict(mode="json")

    async def create_session(
        self,
        agent_id: str,
        environment_id: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            k: v for k, v in (extra or {}).items() if v is not None
        }
        payload["agent"] = agent_id
        payload["environment_id"] = environment_id

        logger.info(
            f"Creating Claude session for agent '{agent_id}' in environment '{environment_id}'"
        )
        session = await self._client.beta.sessions.create(**payload)
        return session.to_dict(mode="json")

    async def send_user_message(
        self, session_id: str, prompt: str
    ) -> BetaManagedAgentsUserMessageEvent:
        logger.info(f"Sending user message to Claude session '{session_id}'")
        response = await self._client.beta.sessions.events.send(
            session_id,
            events=[
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": prompt}],
                }
            ],
        )
        if not response.data:
            raise UnexpectedApiResponseError(
                "User message was sent but no event was returned"
            )
        event = response.data[0]
        if not isinstance(event, BetaManagedAgentsUserMessageEvent):
            raise UnexpectedApiResponseError(
                f"Expected user.message event from send, got {event.type}"
            )
        return event

    def unwrap_webhook(
        self, payload: str, headers: Mapping[str, str]
    ) -> UnwrapWebhookEvent:
        if not self._webhook_signing_secret:
            raise WebhookSigningSecretNotConfiguredError(
                "Webhook signing secret is not configured"
            )
        return self._client.beta.webhooks.unwrap(
            payload, headers=headers, key=self._webhook_signing_secret
        )

    @property
    def has_webhook_secret(self) -> bool:
        return bool(self._webhook_signing_secret)
