from __future__ import annotations

from collections.abc import AsyncGenerator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import anthropic
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
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryConfig


DEFAULT_PAGE_SIZE = 50

_CREATE_RATE_LIMIT_LIMIT_HEADER = "anthropic-ratelimit-requests-limit"
_CREATE_RATE_LIMIT_REMAINING_HEADER = "anthropic-ratelimit-requests-remaining"
_CREATE_RATE_LIMIT_RESET_HEADER = "anthropic-ratelimit-requests-reset"
_WORKSPACE_ID_HEADER = "anthropic-workspace-id"


def _serialize(obj: Any) -> dict[str, Any]:
    """Convert an SDK model instance into a plain JSON-serialisable dict."""
    if hasattr(obj, "to_dict"):
        return obj.to_dict(mode="json")
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return dict(obj)


@dataclass(frozen=True)
class CreateRateLimitInfo:
    """Snapshot of the Managed Agents *create-endpoints* RPM limit.

    Distinct from the (untracked) read-endpoints RPM limit, which is a
    separate pool per Anthropic's Managed Agents rate limits.
    """

    limit: int
    remaining: int
    reset: datetime

    @property
    def seconds_until_reset(self) -> float:
        return max(0.0, (self.reset - datetime.now(timezone.utc)).total_seconds())


class AnthropicClient:
    def __init__(
        self,
        api_host: str,
        api_key: str,
        webhook_signing_secret: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        anthropic_version: str | None = None,
    ) -> None:
        # A dedicated OceanAsyncClient gets us SaaS IP-blocking and consistent SSL
        # verification. Ocean's own retry layer is disabled (max_attempts=0) since
        # the Anthropic SDK already retries internally;
        self._http_client = OceanAsyncClient(
            timeout=ocean.config.client_timeout,
            retry_config=RetryConfig(max_attempts=0),
        )
        default_headers = (
            {"anthropic-version": anthropic_version} if anthropic_version else None
        )
        self._client = AsyncAnthropic(
            api_key=api_key,
            base_url=api_host.rstrip("/"),
            default_headers=default_headers,
            http_client=self._http_client,
        )
        self._webhook_signing_secret = webhook_signing_secret
        self._page_size = page_size
        self._create_rate_limit_info: CreateRateLimitInfo | None = None
        self._workspace_id: str | None = None

    def _capture_create_rate_limit_headers(self, headers: httpx.Headers) -> None:
        limit = headers.get(_CREATE_RATE_LIMIT_LIMIT_HEADER)
        remaining = headers.get(_CREATE_RATE_LIMIT_REMAINING_HEADER)
        reset = headers.get(_CREATE_RATE_LIMIT_RESET_HEADER)
        if limit is None or remaining is None or reset is None:
            return
        try:
            self._create_rate_limit_info = CreateRateLimitInfo(
                limit=int(limit),
                remaining=int(remaining),
                reset=datetime.fromisoformat(reset.replace("Z", "+00:00")),
            )
        except (TypeError, ValueError) as error:
            logger.warning(
                f"Failed to parse Managed Agents create rate limit headers: {error}"
            )

    def get_create_rate_limit_status(self) -> CreateRateLimitInfo | None:
        return self._create_rate_limit_info

    def get_workspace_id(self) -> str | None:
        return self._workspace_id

    async def _paginate(
        self, paginator: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Iterate an SDK auto-paginator and yield records in fixed-size batches."""
        batch: list[dict[str, Any]] = []
        async for item in paginator:
            batch.append(_serialize(item))
            if len(batch) >= self._page_size:
                yield batch
                batch = []
        if batch:
            yield batch

    async def get_agents(
        self, *, include_archived: bool = False
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self._paginate(
            await self._client.beta.agents.list(include_archived=include_archived)
        ):
            yield batch

    async def get_environments(
        self, *, include_archived: bool = False
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self._paginate(
            await self._client.beta.environments.list(include_archived=include_archived)
        ):
            yield batch

    async def get_sessions(
        self, *, include_archived: bool = False
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self._paginate(
            await self._client.beta.sessions.list(include_archived=include_archived)
        ):
            yield batch

    async def get_vaults(
        self, *, include_archived: bool = False
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self._paginate(
            await self._client.beta.vaults.list(include_archived=include_archived)
        ):
            yield batch

    async def get_memory_stores(
        self, *, include_archived: bool = False
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self._paginate(
            await self._client.beta.memory_stores.list(
                include_archived=include_archived
            )
        ):
            yield batch

    async def get_skills(
        self, *, source: Literal["custom", "anthropic"] = "custom"
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self._paginate(
            await self._client.beta.skills.list(source=source)
        ):
            yield batch

    async def get_session(self, session_id: str) -> dict[str, Any]:
        return _serialize(await self._client.beta.sessions.retrieve(session_id))

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
        list_kwargs: dict[str, Any] = {}
        if types is not None:
            list_kwargs["types"] = types
        if order is not None:
            list_kwargs["order"] = order
        if created_at_gt is not None:
            list_kwargs["created_at_gt"] = created_at_gt
        if created_at_gte is not None:
            list_kwargs["created_at_gte"] = created_at_gte
        if created_at_lt is not None:
            list_kwargs["created_at_lt"] = created_at_lt
        if created_at_lte is not None:
            list_kwargs["created_at_lte"] = created_at_lte
        if limit is not None:
            list_kwargs["limit"] = limit

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
        return _serialize(await self._client.beta.vaults.retrieve(vault_id))

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
        try:
            raw = await self._client.beta.agents.with_raw_response.create(**payload)
        except anthropic.APIStatusError as error:
            self._capture_create_rate_limit_headers(error.response.headers)
            raise
        self._capture_create_rate_limit_headers(raw.headers)
        return _serialize(raw.parse())

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
        try:
            raw = await self._client.beta.sessions.with_raw_response.create(**payload)
        except anthropic.APIStatusError as error:
            self._capture_create_rate_limit_headers(error.response.headers)
            raise
        self._capture_create_rate_limit_headers(raw.headers)
        return _serialize(raw.parse())

    async def send_user_message(
        self, session_id: str, prompt: str
    ) -> BetaManagedAgentsUserMessageEvent:
        logger.info(f"Sending user message to Claude session '{session_id}'")
        raw = await self._client.beta.sessions.events.with_raw_response.send(
            session_id,
            events=[
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": prompt}],
                }
            ],
        )
        workspace_id = raw.headers.get(_WORKSPACE_ID_HEADER)
        if workspace_id:
            self._workspace_id = workspace_id
        response = raw.parse()
        if not response.data:
            raise ValueError("User message was sent but no event was returned")
        event = response.data[0]
        if not isinstance(event, BetaManagedAgentsUserMessageEvent):
            raise ValueError(f"Expected user.message event from send, got {event.type}")
        return event

    def unwrap_webhook(
        self, payload: str, headers: Mapping[str, str]
    ) -> UnwrapWebhookEvent:
        if not self._webhook_signing_secret:
            raise ValueError("Webhook signing secret is not configured")
        return self._client.beta.webhooks.unwrap(
            payload, headers=headers, key=self._webhook_signing_secret
        )

    @property
    def has_webhook_secret(self) -> bool:
        return bool(self._webhook_signing_secret)
