from azure_devops.misc import PULL_REQUEST_SEARCH_CRITERIA


def test_completed_and_abandoned_filters_use_closed_time_range() -> None:
    filters_by_status = {
        criteria["searchCriteria.status"]: criteria
        for criteria in PULL_REQUEST_SEARCH_CRITERIA
        if "searchCriteria.status" in criteria
    }

    for status in ("abandoned", "completed"):
        filter_options = filters_by_status[status]
        assert (
            filter_options["searchCriteria.queryTimeRangeType"] == "closed"
        ), f"{status} filter should use closed time range"
