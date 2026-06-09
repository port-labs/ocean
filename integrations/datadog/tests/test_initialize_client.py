import json
from typing import Any, Generator
from unittest.mock import PropertyMock, patch

import pytest

from datadog.exceptions import IntegrationMissingConfigError
from initialize_client import (
    get_credential_map,
    init_client,
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


@pytest.fixture
def patch_integration_config() -> Generator[Any, None, None]:
    """Patch ocean.integration_config so init_client() can read it."""
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
    assert result["org-1"]["datadogApiKey"] == "api-1"


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
    by_org = {c.org_id: c for c in clients}
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
    assert client.org_id is None


# --------------------------------------------------------------------------- #
# init_client (branch selection)
# --------------------------------------------------------------------------- #


def test_init_client_single_org_branch(patch_integration_config: Any) -> None:
    patch_integration_config.return_value = {
        "is_multi_org": False,
        "datadog_base_url": BASE_URL,
        "datadog_api_key": "api",
        "datadog_application_key": "app",
        "datadog_access_token": "token",
    }
    clients = list(init_client())
    assert len(clients) == 1
    assert clients[0].org_id is None


def test_init_client_multi_org_branch(patch_integration_config: Any) -> None:
    patch_integration_config.return_value = {
        "is_multi_org": True,
        "datadog_base_url": BASE_URL,
        "datadog_credential_map": _credential_map_string(),
    }
    clients = list(init_client())
    assert {c.org_id for c in clients} == {"org-1", "org-2"}
