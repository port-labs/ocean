from datetime import datetime, timedelta, timezone

from datadog.incremental import (
    CHANGED_SERVICES_AUDIT_QUERY,
    audit_event_asset_id,
    audit_events_search_body,
    changed_user_id,
    service_name_from_ref,
)

SINCE = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)


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


def test_changed_user_id_returns_the_user_asset() -> None:
    assert changed_user_id(_event("user-1", "/api/v2/users/user-1")) == "user-1"


def test_changed_user_id_skips_role_membership_events() -> None:
    assert changed_user_id(_event("user-1", "/api/v2/roles/role-1/users")) is None


def test_changed_user_id_without_asset_is_none() -> None:
    assert changed_user_id({}) is None


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
