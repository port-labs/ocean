from azure_devops.misc import (
    create_closed_pull_request_search_criteria,
    create_incremental_pull_request_search_criteria,
    ACTIVE_PULL_REQUEST_SEARCH_CRITERIA,
)
from datetime import datetime, timedelta


def test_active_filters() -> None:
    filter_options = ACTIVE_PULL_REQUEST_SEARCH_CRITERIA
    assert (
        filter_options["searchCriteria.status"] == "active"
    ), "active search criteria should use active status"


def test_completed_and_abandoned_filters_use_closed_time_range() -> None:
    min_time_datetime = datetime.now() - timedelta(days=90)
    filters_by_status = {
        criteria["searchCriteria.status"]: criteria
        for criteria in create_closed_pull_request_search_criteria(min_time_datetime)
        if "searchCriteria.status" in criteria
    }

    for status in ("abandoned", "completed"):
        filter_options = filters_by_status[status]
        assert (
            filter_options["searchCriteria.queryTimeRangeType"] == "closed"
        ), f"{status} filter should use closed time range"


def test_incremental_pull_request_search_criteria() -> None:
    cursor = datetime(2026, 6, 1, 12, 0, 0)
    criteria_list = create_incremental_pull_request_search_criteria(cursor)
    assert len(criteria_list) == 3

    active = criteria_list[0]
    assert active["searchCriteria.status"] == "active"
    assert active["searchCriteria.minTime"] == cursor
    assert active["searchCriteria.queryTimeRangeType"] == "created"

    for closed_criteria in criteria_list[1:]:
        assert closed_criteria["searchCriteria.minTime"] == cursor
        assert closed_criteria["searchCriteria.queryTimeRangeType"] == "closed"
