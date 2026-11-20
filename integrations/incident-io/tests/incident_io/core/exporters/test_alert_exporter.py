from datetime import datetime, timezone

from incident_io.core.exporters.alert_exporter import (
    ALERT_PAGE_SIZE,
    AlertExporter,
    build_alert_params,
)
from incident_io.core.options import AlertOptions
from tests.incident_io.core.exporters.helpers import collect, mock_client

ALERT = {
    "id": "01GW2G3V0S59R238FAHPDS1R66",
    "title": "CPU high",
    "status": "firing",
}


def test_build_alert_params_uses_created_at_on_a_full_resync() -> None:
    now = datetime(2026, 11, 19, 23, 30, tzinfo=timezone.utc)
    params = build_alert_params(AlertOptions(days_back=7), now)
    assert params == {"created_at[gte]": "2026-11-12"}


def test_build_alert_params_uses_a_timestamp_cursor() -> None:
    now = datetime(2026, 11, 19, 23, 30, tzinfo=timezone.utc)
    since = datetime(2026, 11, 19, 15, 4, tzinfo=timezone.utc)
    params = build_alert_params(AlertOptions(days_back=30), now, since=since)
    assert params["created_at[gte]"] == "2026-10-20"
    assert params["updated_at[gte]"] == "2026-11-19T15:04:00Z"


def test_build_alert_params_clamps_the_cursor_to_the_window() -> None:
    now = datetime(2026, 11, 19, 23, 30, tzinfo=timezone.utc)
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    params = build_alert_params(AlertOptions(days_back=7), now, since=since)
    assert params["updated_at[gte]"] == "2026-11-12T23:30:00Z"
    assert params["created_at[gte]"] == "2026-11-12"


def test_build_alert_params_adds_statuses() -> None:
    now = datetime(2026, 11, 19, tzinfo=timezone.utc)
    params = build_alert_params(AlertOptions(days_back=30, statuses=["firing"]), now)
    assert params["status[one_of]"] == ["firing"]


async def test_lists_alerts_and_unwraps_one() -> None:
    client = mock_client(
        responses={f"v2/alerts/{ALERT['id']}": {"alert": ALERT}},
        pages=[[ALERT]],
    )
    assert await collect(
        AlertExporter(client).get_paginated_resources(AlertOptions(days_back=30))
    ) == [ALERT]
    (args, kwargs) = client.paginated_calls[0]
    assert args[0] == "v2/alerts"
    assert kwargs["data_key"] == "alerts"
    assert kwargs["page_size"] == ALERT_PAGE_SIZE
    assert "created_at[gte]" in kwargs["params"]
    assert await AlertExporter(client).get_single_resource(ALERT["id"]) == ALERT
