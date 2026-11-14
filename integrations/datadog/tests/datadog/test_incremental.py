from datetime import datetime, timedelta, timezone

from datadog.incremental import (
    audit_event_asset_id,
    audit_events_search_body,
    restricted_resource_id,
)

SINCE = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)


def _event(asset_id: str) -> dict[str, object]:
    return {"attributes": {"attributes": {"asset": {"id": asset_id}}}}


def test_audit_events_search_body_searches_from_cursor_in_utc() -> None:
    cursor = SINCE.astimezone(timezone(timedelta(hours=2)))

    assert audit_events_search_body("@asset.type:slo", cursor) == {
        "filter": {
            "query": "@asset.type:slo",
            "from": "2026-11-05T10:00:00+00:00",
            "to": "now",
        },
        "sort": "-timestamp",
    }


def test_audit_event_asset_id() -> None:
    assert audit_event_asset_id(_event("slo-1")) == "slo-1"
    assert audit_event_asset_id({}) is None


def test_restricted_resource_id_matches_resource_type() -> None:
    assert restricted_resource_id("slo:abc", "slo") == "abc"
    assert restricted_resource_id("monitor:123", "slo") is None
    assert restricted_resource_id("no-type", "slo") is None
