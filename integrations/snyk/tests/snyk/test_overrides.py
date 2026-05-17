import pytest
from pydantic import ValidationError
from snyk.overrides import SnykTargetAPIQueryParams, TargetSelector

from snyk.overrides import (
    SnykPolicyAPIQueryParams,
    SnykProjectAPIQueryParams,
    SnykVulnerabilityAPIQueryParams,
)


def test_generate_query_params_excludes_unset_fields() -> None:
    params = SnykProjectAPIQueryParams()
    assert params.generate_query_params() == {}


def test_generate_query_params_excludes_none_fields() -> None:
    params = SnykProjectAPIQueryParams(ids=None)
    assert "ids" not in params.generate_query_params()


def test_generate_query_params_preserves_list_values() -> None:
    params = SnykProjectAPIQueryParams(
        lifecycle=["production", "development"],
        environment=["frontend", "backend"],
    )
    result = params.generate_query_params()
    assert result["lifecycle"] == ["production", "development"]
    assert result["environment"] == ["frontend", "backend"]


def test_generate_query_params_preserves_scalar_values() -> None:
    params = SnykProjectAPIQueryParams(
        target_reference="main", target_file="package.json"
    )
    result = params.generate_query_params()
    assert result["target_reference"] == "main"
    assert result["target_file"] == "package.json"


def test_merge_with_combines_params_and_extras() -> None:
    params = SnykVulnerabilityAPIQueryParams(status=["open"])
    result = params.merge_with({"version": "2024-06-21", "scan_item.id": "abc"})
    assert result["status"] == ["open"]
    assert result["version"] == "2024-06-21"
    assert result["scan_item.id"] == "abc"


@pytest.mark.parametrize(
    "value",
    [
        "2026-04-15T00:00:00Z",
        "2026-04-15T09:50:54.014Z",
        "2026-04-15T00:00:00+05:30",
    ],
)
def test_vulnerability_date_filter_accepts_valid_formats(value: str) -> None:
    params = SnykVulnerabilityAPIQueryParams(updated_after=value)
    assert params.generate_query_params()["updated_after"] == value


@pytest.mark.parametrize(
    "value",
    [
        "2026-04-15T00:00:00",  # datetime without timezone — rejected by Snyk API
        "2026-04-15",  # bare date — rejected by Snyk API
        "15-04-2026",
        "not-a-date",
    ],
)
def test_vulnerability_date_filter_rejects_invalid_formats(value: str) -> None:
    with pytest.raises(ValidationError):
        SnykVulnerabilityAPIQueryParams(updated_after=value)


def test_merge_with_params_take_precedence_over_extra_values() -> None:
    params = SnykVulnerabilityAPIQueryParams(status=["open"])
    result = params.merge_with({"status": "resolved"})
    assert result["status"] == ["open"]


def test_policy_generate_query_params_excludes_unset_fields() -> None:
    params = SnykPolicyAPIQueryParams()
    assert params.generate_query_params() == {}


def test_policy_generate_query_params_excludes_none_fields() -> None:
    params = SnykPolicyAPIQueryParams(search=None)
    assert "search" not in params.generate_query_params()


def test_policy_generate_query_params_preserves_scalar_search() -> None:
    params = SnykPolicyAPIQueryParams(search="wont-fix")
    assert params.generate_query_params()["search"] == "wont-fix"


def test_policy_generate_query_params_preserves_list_review() -> None:
    params = SnykPolicyAPIQueryParams(review=["pending", "approved"])
    assert params.generate_query_params()["review"] == ["pending", "approved"]


def test_policy_generate_query_params_preserves_bool_expires_never() -> None:
    params = SnykPolicyAPIQueryParams(expires_never=True)
    assert params.generate_query_params()["expires_never"] is True


@pytest.mark.parametrize(
    "value",
    [
        "2024-03-16T00:00:00Z",
        "2024-03-16T09:50:54.014Z",
        "2024-03-16T00:00:00+05:30",
    ],
)
def test_policy_expires_before_accepts_valid_formats(value: str) -> None:
    params = SnykPolicyAPIQueryParams(expires_before=value)
    assert params.generate_query_params()["expires_before"] == value


@pytest.mark.parametrize(
    "value",
    [
        "2024-03-16T00:00:00Z",
        "2024-03-16T09:50:54.014Z",
        "2024-03-16T00:00:00+05:30",
    ],
)
def test_policy_expires_after_accepts_valid_formats(value: str) -> None:
    params = SnykPolicyAPIQueryParams(expires_after=value)
    assert params.generate_query_params()["expires_after"] == value


@pytest.mark.parametrize(
    "value",
    [
        "2024-03-16",
        "16-03-2024",
        "not-a-date",
        "2024-03-16T00:00:00",  # datetime without timezone — rejected by Snyk API
    ],
)
def test_policy_expires_before_rejects_invalid_formats(value: str) -> None:
    with pytest.raises(ValidationError):
        SnykPolicyAPIQueryParams(expires_before=value)


@pytest.mark.parametrize(
    "value",
    [
        "2024-03-16",
        "16-03-2024",
        "not-a-date",
        "2024-03-16T00:00:00",  # datetime without timezone — rejected by Snyk API
    ],
)
def test_policy_expires_after_rejects_invalid_formats(value: str) -> None:
    with pytest.raises(ValidationError):
        SnykPolicyAPIQueryParams(expires_after=value)


def test_policy_merge_with_combines_params_and_extras() -> None:
    params = SnykPolicyAPIQueryParams(search="alice@example.com", review=["pending"])
    result = params.merge_with({"version": "2024-01-01"})
    assert result["search"] == "alice@example.com"
    assert result["review"] == ["pending"]
    assert result["version"] == "2024-01-01"


def test_policy_merge_with_params_take_precedence_over_extra_values() -> None:
    params = SnykPolicyAPIQueryParams(search="wont-fix")
    result = params.merge_with({"search": "old-value"})
    assert result["search"] == "wont-fix"


def test_snyk_target_api_query_params_defaults_generate_empty_dict() -> None:
    params = SnykTargetAPIQueryParams()
    assert params.generate_query_params() == {}


def test_snyk_target_api_query_params_exclude_empty_false_is_included() -> None:
    params = SnykTargetAPIQueryParams(exclude_empty=False)
    assert params.generate_query_params()["exclude_empty"] is False


def test_snyk_target_api_query_params_exclude_empty_true_is_included() -> None:
    params = SnykTargetAPIQueryParams(exclude_empty=True)
    assert params.generate_query_params()["exclude_empty"] is True


def test_snyk_target_api_query_params_is_private_filter() -> None:
    params = SnykTargetAPIQueryParams(is_private=True)
    assert params.generate_query_params()["is_private"] is True


def test_snyk_target_api_query_params_url_filter() -> None:
    params = SnykTargetAPIQueryParams(url="https://github.com/example/repo")
    assert params.generate_query_params()["url"] == "https://github.com/example/repo"


def test_snyk_target_api_query_params_display_name_filter() -> None:
    params = SnykTargetAPIQueryParams(display_name="snyk-fixtures")
    assert params.generate_query_params()["display_name"] == "snyk-fixtures"


@pytest.mark.parametrize(
    "value",
    [
        "2026-05-01T16:00:00Z",
        "2026-05-01T16:00:00.000Z",
        "2026-05-01T16:00:00+05:30",
    ],
)
def test_snyk_target_api_query_params_created_gte_accepts_valid_formats(
    value: str,
) -> None:
    params = SnykTargetAPIQueryParams(created_gte=value)
    assert params.generate_query_params()["created_gte"] == value


@pytest.mark.parametrize(
    "value",
    [
        "2026-05-01",
        "01-05-2026",
        "not-a-date",
        "2026-05-01T16:00:00",  # missing timezone
    ],
)
def test_snyk_target_api_query_params_created_gte_rejects_invalid_formats(
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        SnykTargetAPIQueryParams(created_gte=value)


def test_snyk_target_api_query_params_merge_with_base_params_default_exclude_empty_wins() -> (
    None
):
    params = SnykTargetAPIQueryParams()
    result = params.merge_with({"exclude_empty": False})
    assert result["exclude_empty"] is False


def test_snyk_target_api_query_params_user_exclude_empty_true_overrides_base_default() -> (
    None
):
    params = SnykTargetAPIQueryParams(exclude_empty=True)
    result = params.merge_with({"exclude_empty": False})
    assert result["exclude_empty"] is True


def test_snyk_target_api_query_params_excludes_unset_fields() -> None:
    params = SnykTargetAPIQueryParams(display_name="example")
    result = params.generate_query_params()
    assert "exclude_empty" not in result
    assert "is_private" not in result
    assert "url" not in result


def test_target_selector_default_api_query_params_is_none() -> None:
    selector = TargetSelector(query="true")
    assert selector.api_query_params is None


def test_target_selector_api_query_params_exclude_empty_false() -> None:
    params = SnykTargetAPIQueryParams(exclude_empty=False)
    selector = TargetSelector(query="true", apiQueryParams=params)
    assert selector.api_query_params is not None
    assert selector.api_query_params.exclude_empty is False


def test_target_selector_api_query_params_exclude_empty_true_returns_only_targets_with_projects() -> (
    None
):
    params = SnykTargetAPIQueryParams(exclude_empty=True)
    selector = TargetSelector(query="true", apiQueryParams=params)
    assert selector.api_query_params.exclude_empty is True


def test_target_selector_api_query_params_combined_filters() -> None:
    params = SnykTargetAPIQueryParams(
        exclude_empty=False, is_private=False, display_name="snyk-fixtures"
    )
    selector = TargetSelector(query="true", apiQueryParams=params)
    params = selector.api_query_params.generate_query_params()
    assert params["exclude_empty"] is False
    assert params["is_private"] is False
    assert params["display_name"] == "snyk-fixtures"
