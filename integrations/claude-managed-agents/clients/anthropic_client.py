from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterable, Awaitable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

import httpx
from anthropic import AsyncAnthropic
from anthropic.types.beta import BetaEnvironment, UnwrapWebhookEvent
from anthropic.types.beta.beta_managed_agents_session import BetaManagedAgentsSession
from anthropic.types.beta.sessions.beta_managed_agents_session_event import (
    BetaManagedAgentsSessionEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_user_interrupt_event import (
    BetaManagedAgentsUserInterruptEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_user_interrupt_event_params import (
    BetaManagedAgentsUserInterruptEventParams,
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

WEBHOOKS_BETA = "webhooks-2026-03-01"
WEBHOOK_NAME = "Port Ocean Integration"
# Events this integration's processors handle (catalog sync + trigger_agent).
# Must match Platform's webhook enum (no stream-only names like session.error).
DEFAULT_ENABLED_WEBHOOK_EVENTS = [
    "session.status_run_started",
    "session.status_idled",
    "session.status_rescheduled",
    "session.status_terminated",
    "session.deleted",
    "session.updated",
    "vault.created",
    "vault.archived",
    "vault.deleted",
]

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
        self._api_key = api_key
        self._anthropic_version = anthropic_version
        self._console_host = console_host.rstrip("/")
        self._webhook_signing_secret = webhook_signing_secret
        self._page_size = page_size
        self._create_rate_limit_info: RateLimitInfo | None = None
        self._read_rate_limit_info: RateLimitInfo | None = None
        self._create_rate_limit_lock = asyncio.Lock()
        self._read_rate_limit_lock = asyncio.Lock()
        self._workspace_id: str | None = None
        # Console admin APIs (webhooks) live on platform.claude.com, not the
        # Managed Agents SDK base URL. The SDK only exposes `webhooks.unwrap`.
        self._console_http = OceanAsyncClient(
            timeout=ocean.config.client_timeout,
            retry_config=RetryConfig(max_attempts=3),
        )
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

    async def get_session(self, session_id: str) -> BetaManagedAgentsSession:
        return await self._client.beta.sessions.retrieve(session_id)

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

    async def create_environment(
        self,
        name: str,
        description: str | None = None,
        scope: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description
        if scope:
            payload["scope"] = scope
        if extra:
            payload["config"] = extra

        logger.info(f"Creating Claude environment '{name}'")
        environment = await self._client.beta.environments.create(**payload)
        return environment.to_dict(mode="json")

    async def get_agent(self, agent_id: str) -> dict[str, Any]:
        logger.info(f"Retrieving Claude agent '{agent_id}'")
        agent = await self._client.beta.agents.retrieve(agent_id)
        return agent.to_dict(mode="json")

    async def update_agent(
        self,
        agent_id: str,
        version: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        logger.info(f"Updating Claude agent '{agent_id}' (version {version})")
        agent = await self._client.beta.agents.update(
            agent_id, version=version, **payload
        )
        return agent.to_dict(mode="json")

    async def delete_environment(self, environment_id: str) -> None:
        logger.info(f"Deleting Claude environment '{environment_id}'")
        await self._client.beta.environments.delete(environment_id)

    async def get_environment(self, environment_id: str) -> BetaEnvironment:
        logger.info(f"Retrieving Claude environment '{environment_id}'")
        return await self._client.beta.environments.retrieve(environment_id)

    async def update_environment(
        self,
        environment_id: str,
        payload: dict[str, Any],
    ) -> BetaEnvironment:
        logger.info(f"Updating Claude environment '{environment_id}'")
        return await self._client.beta.environments.update(environment_id, **payload)

    async def archive_agent(self, agent_id: str) -> dict[str, Any]:
        logger.info(f"Archiving Claude agent '{agent_id}'")
        agent = await self._client.beta.agents.archive(agent_id)
        return agent.to_dict(mode="json")

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
    ) -> BetaManagedAgentsSession:
        payload: dict[str, Any] = {
            k: v for k, v in (extra or {}).items() if v is not None
        }
        payload["agent"] = agent_id
        payload["environment_id"] = environment_id

        logger.info(
            f"Creating Claude session for agent '{agent_id}' in environment '{environment_id}'"
        )
        return await self._client.beta.sessions.create(**payload)

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

    async def send_user_interrupt(
        self, session_id: str, session_thread_id: str | None = None
    ) -> BetaManagedAgentsUserInterruptEvent:
        logger.info(f"Interrupting Claude session '{session_id}'")
        event: BetaManagedAgentsUserInterruptEventParams = {"type": "user.interrupt"}
        # Omitted rather than sent as null: the API interrupts every
        # non-archived thread only when the field is absent.
        if session_thread_id:
            event["session_thread_id"] = session_thread_id
        response = await self._client.beta.sessions.events.send(
            session_id,
            events=[event],
        )
        if not response.data:
            raise UnexpectedApiResponseError(
                "Interrupt was sent but no event was returned"
            )
        returned_event = response.data[0]
        if not isinstance(returned_event, BetaManagedAgentsUserInterruptEvent):
            raise UnexpectedApiResponseError(
                f"Expected user.interrupt event from send, got {returned_event.type}"
            )
        return returned_event

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

    def _console_webhook_headers(self) -> dict[str, str]:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-beta": WEBHOOKS_BETA,
            "content-type": "application/json",
        }
        if self._anthropic_version:
            headers["anthropic-version"] = self._anthropic_version
        return headers

    async def _console_request(
        self,
        method: str,
        path: str,
        *,
        json_data: dict[str, Any] | None = None,
        params: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        response = await self._console_http.request(
            method,
            f"{self._console_host}{path}",
            headers=self._console_webhook_headers(),
            json=json_data,
            params=params,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            body = (error.response.text or "")[:500]
            raise httpx.HTTPStatusError(
                f"{error}; body={body}",
                request=error.request,
                response=error.response,
            ) from error
        if not response.content:
            return {}
        return response.json()

    async def list_webhooks(self) -> list[dict[str, Any]]:
        """List Claude Platform webhooks (``has_more`` / ``after_id`` pagination)."""
        webhooks: list[dict[str, Any]] = []
        params: dict[str, str] | None = None
        while True:
            page = await self._console_request("GET", "/v1/webhooks", params=params)
            webhooks.extend(page.get("data") or [])
            if not page.get("has_more"):
                return webhooks
            last_id = page.get("last_id")
            if not isinstance(last_id, str) or not last_id:
                return webhooks
            params = {"after_id": last_id}

    async def create_webhooks_if_not_exists(self, base_url: str) -> None:
        """Upsert a Platform webhook pointing at this integration's public URL.

        Idempotent: if a webhook already targets ``{base_url}/integration/webhook``,
        ensure it is enabled and subscribed to ``DEFAULT_ENABLED_WEBHOOK_EVENTS``.
        Create returns the signing secret once - it is never logged; configure
        ``WEBHOOK_SIGNING_SECRET`` from the Claude Console / create response.
        """
        invoke_url = f"{base_url.rstrip('/')}/integration/webhook"
        desired_events = set(DEFAULT_ENABLED_WEBHOOK_EVENTS)

        try:
            existing = await self.list_webhooks()
        except (httpx.HTTPStatusError, httpx.HTTPError) as error:
            logger.error(f"Failed to list Claude webhooks: {error}")
            return

        for webhook in existing:
            if webhook.get("url") != invoke_url:
                continue

            webhook_id = webhook.get("id")
            if not isinstance(webhook_id, str) or not webhook_id:
                logger.warning(
                    f"Found Claude webhook for {invoke_url} without an id; skipping update"
                )
                return

            current_events = set(webhook.get("enabled_events") or [])
            needs_events = not desired_events.issubset(current_events)
            # Platform uses ``state`` (enabled/disabled), not ``status``.
            needs_enable = webhook.get("state") != "enabled"
            if not needs_events and not needs_enable:
                logger.info(
                    f"Claude webhook {webhook_id} already registered for {invoke_url}"
                )
                return

            update_body: dict[str, Any] = {}
            if needs_events:
                update_body["enabled_events"] = sorted(desired_events)
            if needs_enable:
                update_body["state"] = "enabled"

            try:
                # Platform update is POST /v1/webhooks/{id} (not PATCH).
                await self._console_request(
                    "POST", f"/v1/webhooks/{webhook_id}", json_data=update_body
                )
                logger.info(
                    f"Updated Claude webhook {webhook_id} for {invoke_url} "
                    f"(events={needs_events}, enable={needs_enable})"
                )
            except (httpx.HTTPStatusError, httpx.HTTPError) as error:
                logger.error(f"Failed to update Claude webhook {webhook_id}: {error}")
            return

        body = {
            "url": invoke_url,
            "name": WEBHOOK_NAME,
            "description": "Port Ocean Claude Managed Agents live events",
            "enabled_events": list(DEFAULT_ENABLED_WEBHOOK_EVENTS),
        }
        try:
            created = await self._console_request(
                "POST", "/v1/webhooks", json_data=body
            )
        except (httpx.HTTPStatusError, httpx.HTTPError) as error:
            logger.error(f"Failed to create Claude webhook for {invoke_url}: {error}")
            return

        webhook_id = created.get("id")
        logger.info(f"Created Claude webhook {webhook_id} for {invoke_url}")
        if created.get("signing_secret") and not self._webhook_signing_secret:
            logger.warning(
                "Claude returned a webhook signing secret on create (shown only once). "
                "Set OCEAN__INTEGRATION__CONFIG__WEBHOOK_SIGNING_SECRET from the create "
                "response or Claude Console; it is not logged here."
            )
