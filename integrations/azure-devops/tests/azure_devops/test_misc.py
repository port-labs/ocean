from azure_devops.misc import (
    create_closed_pull_request_search_criteria,
    extract_org_name_from_url,
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


def test_extract_org_name_from_dev_azure_com_url() -> None:
    assert extract_org_name_from_url("https://dev.azure.com/myorg") == "myorg"


def test_extract_org_name_from_dev_azure_com_url_with_trailing_slash() -> None:
    assert extract_org_name_from_url("https://dev.azure.com/myorg/") == "myorg"


def test_extract_org_name_from_dev_azure_com_url_with_path_suffix() -> None:
    # Only the first path segment is the org.
    assert extract_org_name_from_url("https://dev.azure.com/myorg/project") == "myorg"


def test_extract_org_name_from_visualstudio_com_url() -> None:
    assert extract_org_name_from_url("https://myorg.visualstudio.com") == "myorg"


def test_extract_org_name_from_visualstudio_com_url_with_trailing_slash() -> None:
    assert extract_org_name_from_url("https://myorg.visualstudio.com/") == "myorg"


def test_extract_org_name_from_visualstudio_com_url_with_project_path() -> None:
    # Legacy hosts must use the subdomain even when a path segment is present.
    assert (
        extract_org_name_from_url("https://myorg.visualstudio.com/SomeProject")
        == "myorg"
    )


def test_extract_org_name_from_visualstudio_com_url_with_collection_path() -> None:
    assert (
        extract_org_name_from_url(
            "https://myorg.visualstudio.com/DefaultCollection/Project"
        )
        == "myorg"
    )


def test_extract_org_name_from_visualstudio_com_url_is_case_insensitive_host() -> None:
    # Host match is case-insensitive; subdomain casing is preserved.
    assert (
        extract_org_name_from_url("https://MyOrg.VisualStudio.com/Project") == "MyOrg"
    )


def test_extract_org_name_from_dev_azure_com_url_with_deep_path() -> None:
    assert (
        extract_org_name_from_url("https://dev.azure.com/myorg/project/_git/repo")
        == "myorg"
    )
