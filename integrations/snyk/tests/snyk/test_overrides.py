import pytest
from pydantic import ValidationError

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
