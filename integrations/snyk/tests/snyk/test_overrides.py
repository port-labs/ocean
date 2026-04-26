import pytest
from pydantic import ValidationError

from snyk.overrides import SnykProjectAPIQueryParams, SnykVulnerabilityAPIQueryParams


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
