import pytest

from incident_io.helpers.utils import (
    required_permission,
    resolve_api_base_url,
    safe_resource_id,
)


def test_required_permission_matches_known_prefixes() -> None:
    assert required_permission("v2/users") == "users.view"
    assert required_permission("/v2/users/abc") == "users.view"
    assert required_permission("v3/teams") == "catalog_entries.view"
    assert required_permission("v2/schedules/abc") == "schedules.view"
    assert required_permission("v2/incidents") is None


def test_resolve_api_base_url_defaults_and_strips_path() -> None:
    assert resolve_api_base_url(None) == "https://api.incident.io"
    assert (
        resolve_api_base_url("https://api.incident.io/v2") == "https://api.incident.io"
    )


@pytest.mark.parametrize(
    "url", ["http://api.incident.io", "https://user:pw@api.incident.io", ""]
)
def test_resolve_api_base_url_rejects_unsafe_urls(url: str) -> None:
    if url == "":
        assert resolve_api_base_url(url) == "https://api.incident.io"
        return
    with pytest.raises(ValueError):
        resolve_api_base_url(url)


def test_safe_resource_id_rejects_path_characters() -> None:
    assert (
        safe_resource_id("01FDAG4SAP5TYPT98WGR2N7W91") == "01FDAG4SAP5TYPT98WGR2N7W91"
    )
    with pytest.raises(ValueError):
        safe_resource_id("../v2/users")
    with pytest.raises(ValueError):
        safe_resource_id(" id ")
