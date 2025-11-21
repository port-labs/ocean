from unittest.mock import patch

from azure_devops.misc import (
    MAX_NUMBER_OF_DAYS_TO_SEARCH_PULL_REQUESTS,
    create_pull_request_search_criteria,
)


def test_completed_and_abandoned_filters_use_closed_time_range() -> None:
    min_time_in_days = 90
    filters_by_status = {
        criteria["searchCriteria.status"]: criteria
        for criteria in create_pull_request_search_criteria(min_time_in_days)
        if "searchCriteria.status" in criteria
    }

    for status in ("abandoned", "completed"):
        filter_options = filters_by_status[status]
        assert (
            filter_options["searchCriteria.queryTimeRangeType"] == "closed"
        ), f"{status} filter should use closed time range"


def test_completed_and_abandoned_filters_pass_unsupported_min_days() -> None:
    min_time_in_days = 180

    with patch("azure_devops.misc.logger") as mock_logger:
        filters_by_status = {
            criteria["searchCriteria.status"]: criteria
            for criteria in create_pull_request_search_criteria(min_time_in_days)
            if "searchCriteria.status" in criteria
        }

        # Assert warning was logged for invalid min_time_in_days
        mock_logger.warning.assert_called_once_with(
            f"The selector value 'min_time_in_days' ({min_time_in_days}) must be smaller than {MAX_NUMBER_OF_DAYS_TO_SEARCH_PULL_REQUESTS}"
        )

        for status in ("abandoned", "completed"):
            filter_options = filters_by_status[status]
            assert (
                filter_options["searchCriteria.queryTimeRangeType"] == "closed"
            ), f"{status} filter should use closed time range"
