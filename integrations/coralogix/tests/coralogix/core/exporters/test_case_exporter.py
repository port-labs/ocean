from datetime import datetime, timezone

from coralogix.clients.client import PaginationStyle
from coralogix.core.exporters.case_exporter import CaseExporter, build_case_filters
from coralogix.core.options import CaseOptions
from tests.conftest import TEAM_URL, load_example, strip_team
from tests.coralogix.core.exporters.helpers import collect, mock_client

CASE = strip_team(load_example("case"))


def test_build_case_filters_date_range_and_statuses() -> None:
    now = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    filters = build_case_filters(
        CaseOptions(days_back=7, statuses=["CASE_STATUS_ACTIVE"]), now
    )
    assert filters == {
        "dateRange": {
            "from": "2026-11-09T12:00:00.000Z",
            "to": "2026-11-16T12:00:00.000Z",
            "mode": "DATE_RANGE_MODE_CREATED_AT",
        },
        "statuses": ["CASE_STATUS_ACTIVE"],
    }


def test_build_case_filters_uses_cursor_inside_the_lookback() -> None:
    now = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    since = datetime(2026, 11, 16, 11, 0, tzinfo=timezone.utc)
    filters = build_case_filters(CaseOptions(days_back=30), now, since=since)
    assert filters["dateRange"]["from"] == "2026-11-16T11:00:00.000Z"
    assert filters["dateRange"]["to"] == "2026-11-16T12:00:00.000Z"


def test_build_case_filters_does_not_look_further_than_days_back() -> None:
    now = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    filters = build_case_filters(CaseOptions(days_back=7), now, since=since)
    assert filters["dateRange"]["from"] == "2026-11-09T12:00:00.000Z"


def test_build_case_filters_clamps_a_future_cursor_to_now() -> None:
    now = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    since = datetime(2026, 11, 16, 13, 0, tzinfo=timezone.utc)
    filters = build_case_filters(CaseOptions(days_back=7), now, since=since)
    assert filters["dateRange"]["from"] == "2026-11-16T12:00:00.000Z"
    assert filters["dateRange"]["to"] == "2026-11-16T12:00:00.000Z"


def test_build_case_filters_omits_statuses_by_default() -> None:
    now = datetime(2026, 11, 16, tzinfo=timezone.utc)
    assert "statuses" not in build_case_filters(CaseOptions(days_back=30), now)


async def test_posts_paginated_case_search() -> None:
    client = mock_client(pages=[[CASE]])
    cases = await collect(
        CaseExporter(client).get_paginated_resources(CaseOptions(days_back=30))
    )
    assert cases == [{**CASE, "__teamUrl": TEAM_URL}]
    (args, kwargs) = client.paginated_calls[0]
    assert args[0].endswith("cases/cases/v1")
    assert kwargs["method"] == "POST"
    assert kwargs["style"] == PaginationStyle.TOKEN_BODY
    assert kwargs["data_key"] == "cases"
    assert "dateRange" in kwargs["json_data"]["filters"]


async def test_get_single_resource_unwraps_case() -> None:
    client = mock_client({f"cases/cases/v1/{CASE['id']}": {"case": CASE}})
    assert await CaseExporter(client).get_single_resource(CASE["id"]) == CASE
