from __future__ import annotations

from collections.abc import AsyncGenerator, Mapping, Sequence
from datetime import datetime
from typing import Any, Literal

from anthropic import AsyncAnthropic
from anthropic.types.beta import UnwrapWebhookEvent
from anthropic.types.beta.sessions.beta_managed_agents_session_event import (
    BetaManagedAgentsSessionEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_user_message_event import (
    BetaManagedAgentsUserMessageEvent,
)
from loguru import logger

# The Managed Agents API is in beta and requires this fixed beta header on every
# request. The SDK sets it automatically for `client.beta.*` calls; we also set it
# as a default header to make the requirement explicit and future-proof.
MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"
SKILLS_BETA = "skills-2025-10-02"

DEFAULT_PAGE_SIZE = 50


def _serialize(obj: Any) -> dict[str, Any]:
    """Convert an SDK model instance into a plain JSON-serialisable dict."""
    if hasattr(obj, "to_dict"):
        return obj.to_dict(mode="json")
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return dict(obj)


class AnthropicClient:
    """Thin async wrapper around the official Anthropic SDK (Managed Agents beta)."""

    def __init__(
        self,
        api_host: str,
        api_key: str,
        webhook_signing_secret: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> None:
        self._client = AsyncAnthropic(
            api_key=api_key,
            base_url=api_host.rstrip("/"),
            default_headers={"anthropic-beta": MANAGED_AGENTS_BETA},
        )
        self._webhook_signing_secret = webhook_signing_secret
        self._page_size = page_size

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

    def _skills_headers(self) -> dict[str, str]:
        return {"anthropic-beta": SKILLS_BETA}

    async def get_skills(
        self, *, source: Literal["custom", "anthropic"] = "custom"
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self._paginate(
            await self._client.beta.skills.list(
                source=source,
                extra_headers=self._skills_headers(),
            )
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
        """Yield a session's events in batches.

        Session webhooks are thin status pings; the actual conversation (user and
        agent messages, tool use, errors, etc.) lives in the session events API.
        Optional filters are forwarded to ``events.list`` (sorted by ``created_at``).

        Unlike the catalog resources, session events are never mapped to entities;
        they are only logged and used for the run status decision, so the typed SDK
        models are kept instead of being flattened to dicts.
        """
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
        agent = await self._client.beta.agents.create(**payload)
        return _serialize(agent)

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
        return _serialize(session)

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
            raise ValueError("User message was sent but no event was returned")
        event = response.data[0]
        if not isinstance(event, BetaManagedAgentsUserMessageEvent):
            raise ValueError(f"Expected user.message event from send, got {event.type}")
        return event

    def unwrap_webhook(
        self, payload: str, headers: Mapping[str, str]
    ) -> UnwrapWebhookEvent:
        """Verify the Standard Webhooks signature and return the parsed event.

        Raises if the signing secret is missing or the signature is invalid.
        """
        if not self._webhook_signing_secret:
            raise ValueError("Webhook signing secret is not configured")
        return self._client.beta.webhooks.unwrap(
            payload, headers=headers, key=self._webhook_signing_secret
        )

    @property
    def has_webhook_secret(self) -> bool:
        return bool(self._webhook_signing_secret)
