from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import pytest

from incident_io.core.exporters.incident_exporter import (
    IncidentExporter,
    build_incident_params,
)
from incident_io.helpers.exceptions import IncidentIoApiError
from incident_io.core.options import IncidentOptions
from tests.incident_io.core.exporters.helpers import collect, mock_client

INCIDENT = {
    "id": "01FDAG4SAP5TYPT98WGR2N7W91",
    "reference": "INC-123",
    "name": "Our database is sad",
}


def test_build_incident_params_uses_created_at_on_a_full_resync() -> None:
    now = datetime(2026, 11, 19, 23, 0, tzinfo=timezone.utc)
    params = build_incident_params(IncidentOptions(days_back=7), now)
    assert params == {"created_at[gte]": "2026-11-12"}


def test_build_incident_params_uses_cursor_inside_the_lookback() -> None:
    now = datetime(2026, 11, 19, 23, 0, tzinfo=timezone.utc)
    since = datetime(2026, 11, 19, 15, 0, tzinfo=timezone.utc)
    params = build_incident_params(IncidentOptions(days_back=30), now, since=since)
    assert params["created_at[gte]"] == "2026-10-20"
    assert params["updated_at[gte]"] == "2026-11-19"


def test_build_incident_params_does_not_look_further_than_days_back() -> None:
    now = datetime(2026, 11, 19, 23, 0, tzinfo=timezone.utc)
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    params = build_incident_params(IncidentOptions(days_back=7), now, since=since)
    assert params["updated_at[gte]"] == "2026-11-12"
    assert params["created_at[gte]"] == "2026-11-12"


def test_build_incident_params_clamps_a_future_cursor_to_now() -> None:
    now = datetime(2026, 11, 19, 23, 0, tzinfo=timezone.utc)
    since = datetime(2026, 11, 20, 1, 0, tzinfo=timezone.utc)
    params = build_incident_params(IncidentOptions(days_back=7), now, since=since)
    assert params["updated_at[gte]"] == "2026-11-19"


def test_build_incident_params_adds_categories_and_test_modes() -> None:
    now = datetime(2026, 11, 19, tzinfo=timezone.utc)
    params = build_incident_params(
        IncidentOptions(
            days_back=30,
            status_categories=["live", "closed"],
            include_test=True,
        ),
        now,
    )
    assert params["status_category[one_of]"] == ["live", "closed"]
    assert params["mode[one_of]"] == ["standard", "retrospective", "test", "tutorial"]


def test_build_incident_params_adds_severity_ids() -> None:
    now = datetime(2026, 11, 19, tzinfo=timezone.utc)
    params = build_incident_params(
        IncidentOptions(days_back=30), now, severity_ids=["sev-critical", "sev-major"]
    )
    assert params["severity[one_of]"] == ["sev-critical", "sev-major"]


async def test_lists_incidents_with_the_window() -> None:
    client = mock_client(pages=[[INCIDENT]])
    incidents = await collect(
        IncidentExporter(client).get_paginated_resources(IncidentOptions(days_back=30))
    )
    assert incidents == [INCIDENT]
    (args, kwargs) = client.paginated_calls[0]
    assert args[0] == "v2/incidents"
    assert kwargs["data_key"] == "incidents"
    assert "created_at[gte]" in kwargs["params"]
    assert "updated_at[gte]" not in kwargs["params"]


async def test_get_single_resource_unwraps_incident() -> None:
    client = mock_client({f"v2/incidents/{INCIDENT['id']}": {"incident": INCIDENT}})
    assert (
        await IncidentExporter(client).get_single_resource(INCIDENT["id"]) == INCIDENT
    )


async def test_severity_names_are_resolved_before_the_list_call() -> None:
    async def send_paginated_request(
        endpoint: str, data_key: str, **kwargs: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        client.paginated_calls.append((endpoint, data_key, kwargs))
        if data_key == "severities":
            yield [
                {"id": "sev-critical", "name": "Critical"},
                {"id": "sev-major", "name": "Major"},
            ]
            return
        yield [INCIDENT]

    client = mock_client()
    client.send_paginated_request = send_paginated_request
    incidents = await collect(
        IncidentExporter(client).get_paginated_resources(
            IncidentOptions(days_back=30, severities=["critical", "sev-major"])
        )
    )
    assert incidents == [INCIDENT]
    severity_call, incident_call = client.paginated_calls
    assert severity_call[0] == "v1/severities"
    assert incident_call[2]["params"]["severity[one_of]"] == [
        "sev-critical",
        "sev-major",
    ]


async def test_unknown_severity_fails_with_the_known_names() -> None:
    async def send_paginated_request(
        endpoint: str, data_key: str, **kwargs: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [{"id": "sev-info", "name": "Info"}]

    client = mock_client()
    client.send_paginated_request = send_paginated_request
    with pytest.raises(IncidentIoApiError, match="Info"):
        await collect(
            IncidentExporter(client).get_paginated_resources(
                IncidentOptions(days_back=30, severities=["Critical"])
            )
        )


async def test_get_single_resource_rejects_a_path_id() -> None:
    client = mock_client()
    with pytest.raises(ValueError):
        await IncidentExporter(client).get_single_resource("a/b")
