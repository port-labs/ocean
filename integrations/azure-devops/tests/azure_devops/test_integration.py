from integration import AzureDevopsUserSelector

from azure_devops.client.user_sources import (
    EntitlementsUserSource,
    GraphUserSource,
)


def _user_selector(**kwargs: object) -> AzureDevopsUserSelector:
    return AzureDevopsUserSelector.parse_obj({"query": "true", **kwargs})


def test_user_selector_entitlements_is_default_with_no_params() -> None:
    selector = _user_selector()
    assert selector.source == "entitlements"
    source = selector.build_source()
    assert isinstance(source, EntitlementsUserSource)
    assert source.to_params() == {}


def test_user_selector_graph_forwards_subject_types() -> None:
    source = _user_selector(source="graph", subjectTypes=["aad", "svc"]).build_source()
    assert isinstance(source, GraphUserSource)
    assert source.to_params() == {"subjectTypes": "aad,svc"}


def test_user_selector_entitlements_maps_include_fields_and_api_version() -> None:
    source = _user_selector(
        source="entitlements",
        includeFields=["license", "projects"],
        apiVersion="7.1",
    ).build_source()
    assert isinstance(source, EntitlementsUserSource)
    assert source.to_params() == {
        "select": "license,projects",
        "api-version": "7.1",
    }


def test_user_selector_entitlements_excludes_graph_only_fields() -> None:
    source = _user_selector(source="entitlements", subjectTypes=["aad"]).build_source()
    assert isinstance(source, EntitlementsUserSource)
    params = source.to_params()
    assert "subjectTypes" not in params
    assert "source" not in params
