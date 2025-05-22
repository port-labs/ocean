from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import delete, select

from port_ocean.database.manager import DatabaseManager
from port_ocean.database.models.cache import CacheEntry
from port_ocean.cache.base import CacheProvider


class DatabaseCacheProvider(CacheProvider):
    """Database cache provider that uses SQLAlchemy for storage."""

    STORAGE_TYPE = "database"

    def __init__(self, database_manager: DatabaseManager) -> None:
        self._database_manager = database_manager

    async def get(self, key: str) -> Optional[Any]:
        async with await self._database_manager.get_session() as session:
            results = (
                (
                    await session.execute(
                        select(CacheEntry)
                        .where(CacheEntry.cache_key == key)
                        .order_by(CacheEntry.created_at)
                    )
                )
                .scalars()
                .all()
            )

            if not results:
                return None

            if len(results) == 1:
                return results[0].result

            return [result.result for result in results]

    async def set(self, key: str, value: Any) -> None:
        async with await self._database_manager.get_session() as session:
            if isinstance(value, list):
                for item in value:
                    cache_entry = CacheEntry(
                        cache_key=key,
                        result=item,
                        created_at=datetime.now(timezone.utc),
                    )
                    session.add(cache_entry)
            else:
                cache_entry = CacheEntry(
                    cache_key=key,
                    result=value,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(cache_entry)

            await session.commit()

    async def clear(self) -> None:
        """Clear all values from the database cache."""
        async with await self._database_manager.get_session() as session:
            await session.execute(delete(CacheEntry))
            await session.commit()
