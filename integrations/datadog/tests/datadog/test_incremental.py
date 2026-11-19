from datetime import datetime, timedelta, timezone

from datadog.incremental import (
    CHANGED_SERVICES_AUDIT_QUERY,
    audit_event_asset_id,
    audit_event_path,
    audit_events_search_body,
    restricted_resource_id,
    service_name_from_ref,
    windows_ending_after,
)

SINCE = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)


def test_windows_ending_after_keeps_open_and_just_closed_windows() -> None:
    since_ts = int(SINCE.timestamp())
    windows = [
        (since_ts - 200, since_ts - 100),  # closed before since
        (since_ts - 100, since_ts),  # ends exactly at since
        (since_ts - 50, since_ts + 50),  # closed after since
        (since_ts + 50, since_ts + 150),  # still open
    ]

    assert windows_ending_after(windows, SINCE) == windows[2:]


def test_audit_events_search_body_searches_from_since_in_utc() -> None:
    since = SINCE.astimezone(timezone(timedelta(hours=2)))

    assert audit_events_search_body("@asset.type:user", since) == {
        "filter": {
            "query": "@asset.type:user",
            "from": "2026-11-05T10:00:00+00:00",
            "to": "now",
        },
        "sort": "-timestamp",
    }


def _event(asset_id: str, path: str) -> dict[str, object]:
    return {
        "attributes": {
            "attributes": {
                "asset": {"id": asset_id},
                "http": {"url_details": {"path": path}},
            }
        }
    }


def test_audit_event_path_returns_the_request_path() -> None:
    assert (
        audit_event_path(_event("user-1", "/api/v2/roles/role-1/users"))
        == "/api/v2/roles/role-1/users"
    )


def test_audit_event_path_without_http_details_is_empty() -> None:
    assert audit_event_path({}) == ""


def test_changed_services_query_escapes_the_ref_colon() -> None:
    # Unescaped, Datadog rejects the query; quoted, the `*` is no longer a wildcard
    assert CHANGED_SERVICES_AUDIT_QUERY == (
        '@evt.name:"Internal Developer Portal" @asset.type:idp_entity '
        "@action:(created OR modified) @asset.id:service\\:*"
    )


def test_audit_event_asset_id() -> None:
    event = {"attributes": {"attributes": {"asset": {"id": "slo-1"}}}}
    assert audit_event_asset_id(event) == "slo-1"
    assert audit_event_asset_id({}) is None


def test_service_name_from_ref() -> None:
    assert service_name_from_ref("service:default/checkout") == "checkout"
    assert service_name_from_ref("service:payments/checkout") == "checkout"
    assert service_name_from_ref("datastore:default/orders-db") is None
    assert service_name_from_ref("service:no-namespace") is None


def test_restricted_resource_id_matches_resource_type() -> None:
    assert restricted_resource_id("slo:abc", "slo") == "abc"
    assert restricted_resource_id("monitor:123", "slo") is None
    assert restricted_resource_id("no-type", "slo") is None
