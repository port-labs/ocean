from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

# Process-local markers — survive across polling cycles within the same process.
_in_process_last_sync: Optional[datetime] = None
_in_process_last_full_sync: Optional[datetime] = None


async def get_last_sync_time() -> Optional[datetime]:
    if _in_process_last_sync is not None:
        logger.debug(
            f"Using in-process sync marker: {_in_process_last_sync.isoformat()}"
        )
    return _in_process_last_sync


async def set_last_sync_time(dt: datetime) -> None:
    global _in_process_last_sync
    _in_process_last_sync = dt
    logger.info(f"Saved last sync marker: {dt.isoformat()}")


async def get_last_full_sync_time() -> Optional[datetime]:
    return _in_process_last_full_sync


async def set_last_full_sync_time(dt: datetime) -> None:
    global _in_process_last_full_sync
    _in_process_last_full_sync = dt
    logger.info(f"Saved last full-sync marker: {dt.isoformat()}")


def is_full_sync_due(
    now: datetime,
    last_full_sync: Optional[datetime],
    full_sync_interval_minutes: int,
) -> bool:
    """Decide whether the current run should bypass the delta marker.

    Returns True when:
      * full_sync_interval_minutes <= 0 (operator opted into always-full), or
      * no full sync has been recorded yet (first run after startup), or
      * the elapsed time since the last full sync meets/exceeds the interval.
    """
    if full_sync_interval_minutes <= 0:
        return True
    if last_full_sync is None:
        return True
    return now - last_full_sync >= timedelta(minutes=full_sync_interval_minutes)
