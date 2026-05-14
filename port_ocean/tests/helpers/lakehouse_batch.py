"""Factories for lakehouse batch ingest tests."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from port_ocean.core.models import (
    LakehouseDataEntry,
    LakehouseDataEntryBatch,
    LakehouseEventType,
    LakehouseOperation,
)


def make_single_entry_lakehouse_batch(
    raw_data: list[dict[str, Any]],
    *,
    kind: str,
    index: int,
    operation: LakehouseOperation = LakehouseOperation.UPSERT,
    resync_start_time: datetime | None = None,
    event_type: LakehouseEventType | None = None,
    event_id: str | None = None,
    extraction_timestamp: int | None = None,
) -> LakehouseDataEntryBatch:
    """Build a batch payload with one data entry (mirrors typical single-chunk sends)."""
    et = event_type or LakehouseEventType.LIVE_EVENT
    ts = (
        extraction_timestamp
        if extraction_timestamp is not None
        else int(datetime.now().timestamp() * 1000)
    )
    entry: LakehouseDataEntry = {
        "request": {},
        "response": {},
        "items": raw_data,
        "metadata": {
            "operation": operation,
            "resource_index": index,
            "extraction_timestamp": ts,
        },
    }
    return {
        "event_id": event_id,
        "type": et.value,
        "kind": kind,
        "event_type": et,
        "resync_start_time": resync_start_time,
        "extraction_timestamp": ts,
        "data": [entry],
    }
