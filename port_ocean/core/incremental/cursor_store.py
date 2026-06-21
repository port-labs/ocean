from datetime import datetime
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from port_ocean.clients.port.client import PortClient


class CursorStore:
    """Persists and retrieves incremental sync cursors via the integ-service cursor API.

    One cursor document exists per ``(integration_id, kind, index)`` triplet.
    The ``index`` corresponds to the position of the resource config block in
    ``port-app-config.yaml``, allowing multiple selectors for the same kind to
    each track their own progress independently.
    """

    def __init__(self, port_client: "PortClient") -> None:
        self._client = port_client

    async def get(self, kind: str, index: int) -> datetime | None:
        """Return the stored cursor for *kind* / *index*, or ``None`` on first run."""
        cursor = await self._client.get_integration_cursor(kind, index)
        if cursor is None:
            logger.debug(
                "No cursor found for kind, will seed from interval",
                kind=kind,
                index=index,
            )
        return cursor

    async def save(self, kind: str, index: int, value: datetime) -> None:
        """Persist *value* as the new cursor for *kind* / *index*."""
        await self._client.upsert_integration_cursor(kind, index, value)
        logger.debug(
            "Cursor saved",
            kind=kind,
            index=index,
            cursor=value.isoformat(),
        )

    async def delete_all(self) -> None:
        """Remove all cursors for this integration.

        Should be called after a successful full resync so the next incremental
        run starts from a clean baseline.
        """
        await self._client.delete_integration_cursors()
        logger.debug("All incremental cursors deleted")
