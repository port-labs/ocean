import pytest

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.user_sources import EntitlementsUserSource


def test_entitlements_user_source_to_params_without_page_size() -> None:
    source = EntitlementsUserSource(
        include_fields=["license", "projects"],
        api_version="7.1",
    )
    assert source.to_params() == {
        "select": "license,projects",
        "api-version": "7.1",
    }


def test_entitlements_user_source_to_params_maps_page_size_for_modern_api_version() -> (
    None
):
    source = EntitlementsUserSource(
        include_fields=["projects", "groupRules"],
        api_version="7.1",
        page_size=10,
    )
    assert source.to_params() == {
        "select": "projects,groupRules",
        "api-version": "7.1",
        "$top": "10",
    }


def test_entitlements_user_source_to_params_maps_page_size_for_legacy_api_version() -> (
    None
):
    source = EntitlementsUserSource(api_version="6.0", page_size=10)
    assert source.to_params() == {
        "api-version": "6.0",
        "top": "10",
    }


@pytest.mark.parametrize(
    ("api_version", "page_size", "expected"),
    [
        ("7.1", 10, {"$top": "10"}),
        ("6.0", 10, {"top": "10"}),
    ],
)
def test_entitlements_page_size_param(
    api_version: str, page_size: int, expected: dict[str, str]
) -> None:
    assert (
        AzureDevopsClient.entitlements_page_size_param(api_version, page_size)
        == expected
    )
