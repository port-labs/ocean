import json
from typing import Any, Generator
from unittest.mock import PropertyMock, patch

import pytest

import client_manager
from datadog.exceptions import IntegrationMissingConfigError
from client_manager import (
    DatadogClientManager,
    get_client_manager,
    get_credential_map,
    init_client_for_multi_org,
    init_client_single_org,
)

BASE_URL = "https://api.datadoghq.com"


def _credential_map_string() -> str:
    return json.dumps(
        {
            "org-1": {"datadogApiKey": "api-1", "datadogApplicationKey": "app-1"},
            "org-2": {"datadogApiKey": "api-2", "datadogApplicationKey": "app-2"},
        }
    )


@pytest.fixture(autouse=True)
def reset_client_manager() -> Generator[None, None, None]:
    """get_client_manager() caches the manager process-wide; reset it around each
    test so config patches take effect."""
    client_manager._client_manager = None
    yield
    client_manager._client_manager = None


@pytest.fixture
def patch_integration_config() -> Generator[Any, None, None]:
    """Patch ocean.integration_config so the client manager can read it."""
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        yield mock_config


# --------------------------------------------------------------------------- #
# get_credential_map
# --------------------------------------------------------------------------- #


def test_get_credential_map_parses_valid_json() -> None:
    config = {"datadog_credential_map": _credential_map_string()}
    result = get_credential_map(config)
    assert set(result.keys()) == {"org-1", "org-2"}
    assert result["org-1"].api_key == "api-1"
    assert result["org-1"].app_key == "app-1"


def test_get_credential_map_missing_raises() -> None:
    with pytest.raises(IntegrationMissingConfigError):
        get_credential_map({})


def test_get_credential_map_invalid_json_raises() -> None:
    with pytest.raises(IntegrationMissingConfigError):
        get_credential_map({"datadog_credential_map": "{not valid json"})


def test_get_credential_map_non_dict_json_raises() -> None:
    with pytest.raises(IntegrationMissingConfigError):
        get_credential_map({"datadog_credential_map": json.dumps(["a", "b"])})


# --------------------------------------------------------------------------- #
# init_client_for_multi_org
# --------------------------------------------------------------------------- #


def test_init_client_for_multi_org_yields_client_per_org() -> None:
    config = {
        "datadog_base_url": BASE_URL,
        "datadog_credential_map": _credential_map_string(),
    }
    clients = list(init_client_for_multi_org(config))

    assert len(clients) == 2
    by_org = {c.org_uuid: c for c in clients}
    assert by_org["org-1"].dd_api_key == "api-1"
    assert by_org["org-1"].dd_app_key == "app-1"
    assert by_org["org-2"].dd_api_key == "api-2"
    assert all(c.api_url == BASE_URL for c in clients)


def test_init_client_for_multi_org_missing_inner_keys_raises() -> None:
    config = {
        "datadog_base_url": BASE_URL,
        "datadog_credential_map": json.dumps({"org-1": {"datadogApiKey": "api-1"}}),
    }
    with pytest.raises(IntegrationMissingConfigError):
        list(init_client_for_multi_org(config))


def test_init_client_for_multi_org_uses_per_org_base_url_with_fallback() -> None:
    other_url = "https://api.us3.datadoghq.com"
    config = {
        "datadog_base_url": BASE_URL,
        "datadog_credential_map": json.dumps(
            {
                # no datadogBaseUrl -> falls back to the integration's base url
                "org-1": {"datadogApiKey": "a1", "datadogApplicationKey": "p1"},
                # overrides with its own site
                "org-2": {
                    "datadogApiKey": "a2",
                    "datadogApplicationKey": "p2",
                    "datadogBaseUrl": other_url,
                },
            }
        ),
    }
    by_org = {c.org_uuid: c for c in init_client_for_multi_org(config)}

    assert by_org["org-1"].api_url == BASE_URL
    assert by_org["org-2"].api_url == other_url


# --------------------------------------------------------------------------- #
# init_client_single_org
# --------------------------------------------------------------------------- #


def test_init_client_single_org_builds_one_client() -> None:
    config = {
        "datadog_base_url": BASE_URL,
        "datadog_api_key": "api",
        "datadog_application_key": "app",
        "datadog_access_token": "token",
    }
    client = init_client_single_org(config)
    assert client.api_url == BASE_URL
    assert client.dd_api_key == "api"
    assert client.dd_app_key == "app"
    assert client.access_token == "token"
    assert client.org_uuid is None


# --------------------------------------------------------------------------- #
# get_client_manager (branch selection + caching)
# --------------------------------------------------------------------------- #


def test_get_client_manager_single_org_branch(patch_integration_config: Any) -> None:
    patch_integration_config.return_value = {
        "datadog_base_url": BASE_URL,
        "datadog_api_key": "api",
        "datadog_application_key": "app",
        "datadog_access_token": "token",
    }
    clients = get_client_manager().clients
    assert len(clients) == 1
    assert clients[0].org_uuid is None


def test_get_client_manager_multi_org_branch(patch_integration_config: Any) -> None:
    patch_integration_config.return_value = {
        "datadog_base_url": BASE_URL,
        "datadog_credential_map": _credential_map_string(),
    }
    clients = get_client_manager().clients
    assert {c.org_uuid for c in clients} == {"org-1", "org-2"}


def test_get_client_manager_is_cached(patch_integration_config: Any) -> None:
    patch_integration_config.return_value = {
        "datadog_base_url": BASE_URL,
        "datadog_api_key": "api",
        "datadog_application_key": "app",
        "datadog_access_token": "token",
    }
    # Repeated calls must hand back the same manager (and the same client
    # instances with their underlying HTTP pools), not freshly constructed ones.
    assert get_client_manager() is get_client_manager()
    assert get_client_manager().clients == get_client_manager().clients


# --------------------------------------------------------------------------- #
# DatadogClientManager
# --------------------------------------------------------------------------- #


def _single_org_config() -> dict[str, Any]:
    return {
        "datadog_base_url": BASE_URL,
        "datadog_api_key": "api",
        "datadog_application_key": "app",
        "datadog_access_token": "token",
    }


def _multi_org_config() -> dict[str, Any]:
    return {
        "datadog_base_url": BASE_URL,
        "datadog_credential_map": _credential_map_string(),
    }


def test_manager_single_org_resolves_sole_client_for_any_org() -> None:
    manager = DatadogClientManager(_single_org_config())
    assert len(manager.clients) == 1
    sole = manager.clients[0]
    assert manager.get_client_by_org_uuid("anything") is sole
    assert manager.get_client_by_org_uuid(None) is sole


def test_manager_multi_org_resolves_by_org_uuid() -> None:
    manager = DatadogClientManager(_multi_org_config())
    assert {c.org_uuid for c in manager.clients} == {"org-1", "org-2"}

    resolved = manager.get_client_by_org_uuid("org-2")
    assert resolved is not None and resolved.org_uuid == "org-2"


def test_manager_multi_org_no_match_returns_none() -> None:
    manager = DatadogClientManager(_multi_org_config())
    assert manager.get_client_by_org_uuid("missing") is None
    assert manager.get_client_by_org_uuid(None) is None
