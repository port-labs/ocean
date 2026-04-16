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


def test_merge_with_extra_values_override_params() -> None:
    params = SnykVulnerabilityAPIQueryParams(status=["open"])
    result = params.merge_with({"status": "resolved"})
    assert result["status"] == "resolved"
