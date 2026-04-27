import pytest
from snyk.utils import parse_next_page_params


BASE = "https://api.snyk.io/rest"


def test_strips_rest_prefix():
    url_path, _ = parse_next_page_params(f"{BASE}/orgs/abc/projects?version=2024-01-01")
    assert url_path.startswith("/orgs/abc/projects")
    assert "/rest" not in url_path


def test_single_value_params_are_strings():
    _, params = parse_next_page_params(
        f"{BASE}/orgs/abc/projects?version=2024-01-01&limit=10"
    )
    assert params["version"] == "2024-01-01"
    assert params["limit"] == "10"


def test_repeated_params_are_lists():
    _, params = parse_next_page_params(
        f"{BASE}/orgs/abc/projects?target_id=aaa&target_id=bbb&target_id=ccc"
    )
    assert params["target_id"] == ["aaa", "bbb", "ccc"]


def test_mixed_single_and_repeated_params():
    _, params = parse_next_page_params(
        f"{BASE}/orgs/abc/issues?version=2024-01-01&status=open&status=resolved&limit=100"
    )
    assert params["version"] == "2024-01-01"
    assert params["limit"] == "100"
    assert params["status"] == ["open", "resolved"]


def test_no_params():
    url_path, params = parse_next_page_params(f"{BASE}/orgs/abc/projects")
    assert url_path == "/orgs/abc/projects"
    assert params == {}


def test_returns_all_keys():
    _, params = parse_next_page_params(
        f"{BASE}/orgs/abc/projects?version=2024-01-01&starting_after=cursor123"
    )
    assert set(params.keys()) == {"version", "starting_after"}


def test_duplicate_key_does_not_drop_values():
    _, params = parse_next_page_params(
        f"{BASE}/orgs/abc/projects?type=npm&type=pip&type=docker"
    )
    assert sorted(params["type"]) == ["docker", "npm", "pip"]
