import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger
from port_ocean.utils.ttl_cache import TTLCache
from pydantic import BaseModel

from claude_managed_agents.clients.anthropic_client import AnthropicClient
from claude_managed_agents.integration import ObjectKind

# Resource kinds a session can reference.
SESSION_REFERENCED_KINDS = (
    ObjectKind.AGENT,
    ObjectKind.ENVIRONMENT,
    ObjectKind.VAULT,
    ObjectKind.MEMORY_STORE,
)

# Archiving is terminal, so only archived resources are cached. Active ones are
# always looked up again, since they can be archived at any moment while their
# sessions keep running.
ARCHIVED_CACHE_TTL_SECONDS = 24 * 60 * 60
ARCHIVED_CACHE_MAX_ITEMS = 10_000
_archived_resources_cache = TTLCache[bool](
    ttl_seconds=ARCHIVED_CACHE_TTL_SECONDS, max_items=ARCHIVED_CACHE_MAX_ITEMS
)


class ArchivableResource(BaseModel):
    id: str
    archived_at: str | None = None


class SessionAgent(BaseModel):
    id: str | None = None


class SessionResource(BaseModel):
    type: str | None = None
    memory_store_id: str | None = None


class SessionReferences(BaseModel):
    """The parts of a session that link it to other resources. Mirrors the
    session relations in `port-app-config.yml`."""

    agent: SessionAgent | None = None
    environment_id: str | None = None
    vault_ids: list[str] | None = None
    resources: list[SessionResource] | None = None

    def referenced_ids(self) -> dict[ObjectKind, set[str]]:
        return {
            ObjectKind.AGENT: (
                {self.agent.id} if self.agent and self.agent.id else set()
            ),
            ObjectKind.ENVIRONMENT: (
                {self.environment_id} if self.environment_id else set()
            ),
            ObjectKind.VAULT: set(self.vault_ids or []),
            ObjectKind.MEMORY_STORE: {
                resource.memory_store_id
                for resource in self.resources or []
                if resource.type == "memory_store" and resource.memory_store_id
            },
        }


class ArchivedResourceChecker:
    """Tells whether a session references an archived resource.

    Resyncs call `load_archived_ids` once to list every archived resource up
    front, while webhook events (which have no resync context) look resources up
    one by one.
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
        referenced = SessionReferences.model_validate(session).referenced_ids()

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
                resource = ArchivableResource.model_validate(
                    item.to_dict(mode="json", warnings=False)
                )
                if resource.archived_at:
                    archived_ids.add(resource.id)
        return archived_ids

    def _retrievers(self) -> dict[ObjectKind, Callable[[str], Awaitable[Any]]]:
        return {
            ObjectKind.AGENT: self._client.get_agent,
            ObjectKind.ENVIRONMENT: self._client.get_environment,
            ObjectKind.VAULT: self._client.get_vault,
            ObjectKind.MEMORY_STORE: self._client.get_memory_store,
        }

    async def _is_archived(self, kind: ObjectKind, resource_id: str) -> bool:
        cache_key = f"{kind}:{resource_id}"
        if _archived_resources_cache.get(cache_key):
            return True

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
        if archived:
            _archived_resources_cache.set(cache_key, True)
        return archived
