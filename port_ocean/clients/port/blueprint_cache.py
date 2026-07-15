import time
from dataclasses import dataclass

from port_ocean.core.models import Blueprint


@dataclass
class BlueprintCacheEntry:
    blueprint: Blueprint
    cached_at: float


class BlueprintCache:
    def __init__(self, ttl_seconds: float) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, BlueprintCacheEntry] = {}

    def get(self, identifier: str) -> BlueprintCacheEntry | None:
        entry = self._entries.get(identifier)
        if entry is None:
            return None
        if time.monotonic() - entry.cached_at >= self._ttl_seconds:
            del self._entries[identifier]
            return None
        return entry

    def set(self, blueprint: Blueprint) -> None:
        self._entries[blueprint.identifier] = BlueprintCacheEntry(
            blueprint=blueprint,
            cached_at=time.monotonic(),
        )

    def invalidate(self, identifier: str) -> None:
        self._entries.pop(identifier, None)

    def invalidate_all(self) -> None:
        self._entries.clear()
