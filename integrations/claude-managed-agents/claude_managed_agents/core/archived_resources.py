import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from claude_managed_agents.clients.anthropic_client import AnthropicClient
from claude_managed_agents.integration import ObjectKind

# Archiving is terminal, so an archived resource never becomes active again and
# is cached for good. Active resources are re-checked after this TTL.
ACTIVE_STATE_CACHE_TTL_SECONDS = 300.0

# Resource kinds a session can reference.
SESSION_REFERENCED_KINDS = (
    ObjectKind.AGENT,
    ObjectKind.ENVIRONMENT,
    ObjectKind.VAULT,
    ObjectKind.MEMORY_STORE,
)

# (kind, resource id) -> (is archived, monotonic expiry)
_archive_state_cache: dict[tuple[ObjectKind, str], tuple[bool, float]] = {}


def clear_archive_state_cache() -> None:
    _archive_state_cache.clear()


def get_session_referenced_ids(session: dict[str, Any]) -> dict[ObjectKind, set[str]]:
    """Mirrors the session relations in `port-app-config.yml`."""
    agent = session.get("agent") or {}
    resources = session.get("resources") or []
    return {
        ObjectKind.AGENT: {agent["id"]} if agent.get("id") else set(),
        ObjectKind.ENVIRONMENT: (
            {session["environment_id"]} if session.get("environment_id") else set()
        ),
        ObjectKind.VAULT: set(session.get("vault_ids") or []),
        ObjectKind.MEMORY_STORE: {
            resource["memory_store_id"]
            for resource in resources
            if resource.get("type") == "memory_store"
            and resource.get("memory_store_id")
        },
    }


class ArchivedResourceChecker:
    """Tells whether a session references an archived resource.

    Resyncs call `load_archived_ids` once to list every archived resource up
    front, while webhook events (which have no resync context) look resources up
    one by one and cache the answer.
    """

    def __init__(self, client: AnthropicClient) -> None:
        self._client = client
        self._archived_ids: dict[ObjectKind, set[str]] | None = None

    async def load_archived_ids(self) -> None:
        beta = self._client.beta
        list_calls: dict[ObjectKind, Awaitable[Any]] = {
            ObjectKind.AGENT: beta.agents.list(include_archived=True),
            ObjectKind.ENVIRONMENT: beta.environments.list(include_archived=True),
            ObjectKind.VAULT: beta.vaults.list(include_archived=True),
            ObjectKind.MEMORY_STORE: beta.memory_stores.list(include_archived=True),
        }
        archived = await asyncio.gather(
            *(self._collect_archived_ids(call) for call in list_calls.values())
        )
        self._archived_ids = dict(zip(list_calls, archived))
        logger.info(
            "Loaded archived resource ids: "
            + ", ".join(
                f"{kind}={len(ids)}" for kind, ids in self._archived_ids.items()
            )
        )

    async def session_references_archived_resource(
        self, session: dict[str, Any]
    ) -> bool:
        referenced = get_session_referenced_ids(session)

        if self._archived_ids is not None:
            return any(
                referenced[kind] & self._archived_ids[kind]
                for kind in SESSION_REFERENCED_KINDS
            )

        checks = [
            self._is_archived(kind, resource_id)
            for kind in SESSION_REFERENCED_KINDS
            for resource_id in referenced[kind]
        ]
        return any(await asyncio.gather(*checks))

    async def _collect_archived_ids(self, list_call: Awaitable[Any]) -> set[str]:
        archived_ids: set[str] = set()
        async for batch in self._client.paginate(list_call):
            for item in batch:
                raw = item.to_dict(mode="json", warnings=False)
                if raw.get("archived_at"):
                    archived_ids.add(str(raw["id"]))
        return archived_ids

    def _retrievers(self) -> dict[ObjectKind, Callable[[str], Awaitable[Any]]]:
        return {
            ObjectKind.AGENT: self._client.get_agent,
            ObjectKind.ENVIRONMENT: self._client.get_environment,
            ObjectKind.VAULT: self._client.get_vault,
            ObjectKind.MEMORY_STORE: self._client.get_memory_store,
        }

    async def _is_archived(self, kind: ObjectKind, resource_id: str) -> bool:
        key = (kind, resource_id)
        cached = _archive_state_cache.get(key)
        if cached is not None and cached[1] > time.monotonic():
            return cached[0]

        try:
            resource = await self._retrievers()[kind](resource_id)
        except Exception as error:
            # A resource we cannot read (e.g. already deleted) is not archived;
            # keep the session rather than hide it on a lookup failure.
            logger.warning(
                f"Could not check whether {kind} {resource_id} is archived: {error}"
            )
            return False

        archived = bool(getattr(resource, "archived_at", None))
        expires_at = (
            float("inf")
            if archived
            else time.monotonic() + ACTIVE_STATE_CACHE_TTL_SECONDS
        )
        _archive_state_cache[key] = (archived, expires_at)
        return archived
