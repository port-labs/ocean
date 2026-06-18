import json
from typing import Any, Generator
from unittest.mock import AsyncMock, PropertyMock, patch

import httpx
import pytest

import client_manager
from datadog.client import DatadogClient
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
        [
            {"datadogApiKey": "api-1", "datadogApplicationKey": "app-1"},
            {"datadogApiKey": "api-2", "datadogApplicationKey": "app-2"},
        ]
    )


def _stub_org(client: DatadogClient, public_id: str, name: str) -> None:
    client.send_api_request = AsyncMock(  # type: ignore[method-assign]
        return_value={"orgs": [{"public_id": public_id, "name": name}]}
    )


async def _build_enriched_manager(
    orgs: list[tuple[str, str]],
) -> DatadogClientManager:
    """Build a multi-org manager whose clients resolve to the given (id, name) orgs."""
    creds = [
        {"datadogApiKey": f"api-{i}", "datadogApplicationKey": f"app-{i}"}
        for i in range(len(orgs))
    ]
    config = {"datadog_base_url": BASE_URL, "datadog_credential_map": json.dumps(creds)}
    manager = DatadogClientManager(config)
    for client, (public_id, name) in zip(manager.clients, orgs):
        _stub_org(client, public_id, name)
    await manager.validate_and_enrich()
    return manager


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
    assert [entry.api_key for entry in result] == ["api-1", "api-2"]
    assert result[0].app_key == "app-1"
    assert result[0].base_url is None


def test_get_credential_map_missing_raises() -> None:
    with pytest.raises(IntegrationMissingConfigError):
        get_credential_map({})


def test_get_credential_map_invalid_json_raises() -> None:
    with pytest.raises(IntegrationMissingConfigError):
        get_credential_map({"datadog_credential_map": "{not valid json"})


def test_get_credential_map_non_list_json_raises() -> None:
    # The map must be a JSON array, not an object.
    with pytest.raises(IntegrationMissingConfigError):
        get_credential_map({"datadog_credential_map": json.dumps({"a": "b"})})


# --------------------------------------------------------------------------- #
# init_client_for_multi_org
# --------------------------------------------------------------------------- #


def test_init_client_for_multi_org_yields_client_per_entry() -> None:
    config = {
        "datadog_base_url": BASE_URL,
        "datadog_credential_map": _credential_map_string(),
    }
    clients = list(init_client_for_multi_org(config))

    assert len(clients) == 2
    assert {c.dd_api_key for c in clients} == {"api-1", "api-2"}
    # org identity is unknown until validate_and_enrich() runs
    assert all(c.org_id is None and c.org_name is None for c in clients)
    assert all(c.api_url == BASE_URL for c in clients)


def test_init_client_for_multi_org_missing_inner_keys_raises() -> None:
    config = {
        "datadog_base_url": BASE_URL,
        "datadog_credential_map": json.dumps([{"datadogApiKey": "api-1"}]),
    }
    with pytest.raises(IntegrationMissingConfigError):
        list(init_client_for_multi_org(config))


def test_init_client_for_multi_org_uses_per_org_base_url_with_fallback() -> None:
    other_url = "https://api.us3.datadoghq.com"
    config = {
        "datadog_base_url": BASE_URL,
        "datadog_credential_map": json.dumps(
            [
                {"datadogApiKey": "a1", "datadogApplicationKey": "p1"},
                {
                    "datadogApiKey": "a2",
                    "datadogApplicationKey": "p2",
                    "datadogBaseUrl": other_url,
                },
            ]
        ),
    }
    by_key = {c.dd_api_key: c for c in init_client_for_multi_org(config)}

    assert by_key["a1"].api_url == BASE_URL
    assert by_key["a2"].api_url == other_url


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
    assert client.org_name is None


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
    manager = get_client_manager()
    assert manager.is_multi_org is False
    assert len(manager.clients) == 1


def test_get_client_manager_multi_org_branch(patch_integration_config: Any) -> None:
    patch_integration_config.return_value = {
        "datadog_base_url": BASE_URL,
        "datadog_credential_map": _credential_map_string(),
    }
    manager = get_client_manager()
    assert manager.is_multi_org is True
    assert {c.dd_api_key for c in manager.clients} == {"api-1", "api-2"}


def test_get_client_manager_is_cached(patch_integration_config: Any) -> None:
    patch_integration_config.return_value = {
        "datadog_base_url": BASE_URL,
        "datadog_api_key": "api",
        "datadog_application_key": "app",
        "datadog_access_token": "token",
    }
    assert get_client_manager() is get_client_manager()


# --------------------------------------------------------------------------- #
# validate_and_enrich
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_validate_and_enrich_tags_clients_with_org_identity() -> None:
    manager = await _build_enriched_manager(
        [("uuid-1", "DPN | Port"), ("uuid-2", "Demo")]
    )
    by_key = {c.dd_api_key: c for c in manager.clients}
    assert (by_key["api-0"].org_id, by_key["api-0"].org_name) == ("uuid-1", "DPN | Port")
    assert (by_key["api-1"].org_id, by_key["api-1"].org_name) == ("uuid-2", "Demo")


@pytest.mark.asyncio
async def test_validate_and_enrich_drops_clients_with_invalid_keys() -> None:
    config = {
        "datadog_base_url": BASE_URL,
        "datadog_credential_map": _credential_map_string(),
    }
    manager = DatadogClientManager(config)
    good, bad = manager.clients
    _stub_org(good, "uuid-good", "Good Org")
    request = httpx.Request("GET", f"{BASE_URL}/api/v1/org")
    bad.send_api_request = AsyncMock(  # type: ignore[method-assign]
        side_effect=httpx.HTTPStatusError(
            "forbidden", request=request, response=httpx.Response(403, request=request)
        )
    )

    await manager.validate_and_enrich()

    assert [c.org_name for c in manager.clients] == ["Good Org"]
    assert manager.get_clients_by_org_id("uuid-good") == [good]


@pytest.mark.asyncio
async def test_validate_and_enrich_is_noop_for_single_org() -> None:
    config = {
        "datadog_base_url": BASE_URL,
        "datadog_api_key": "api",
        "datadog_application_key": "app",
        "datadog_access_token": "token",
    }
    manager = DatadogClientManager(config)
    sole = manager.clients[0]
    sole.send_api_request = AsyncMock()  # type: ignore[method-assign]

    await manager.validate_and_enrich()

    sole.send_api_request.assert_not_called()
    assert manager.clients == [sole]


# --------------------------------------------------------------------------- #
# routing
# --------------------------------------------------------------------------- #


def test_single_org_resolves_sole_client_for_any_lookup() -> None:
    config = {
        "datadog_base_url": BASE_URL,
        "datadog_api_key": "api",
        "datadog_application_key": "app",
        "datadog_access_token": "token",
    }
    manager = DatadogClientManager(config)
    sole = manager.clients[0]
    assert manager.get_clients_by_org_id("anything") == [sole]
    assert manager.get_clients_by_org_name("anything") == [sole]


@pytest.mark.asyncio
async def test_get_clients_by_org_id_routes_audit_events() -> None:
    manager = await _build_enriched_manager(
        [("uuid-1", "Org One"), ("uuid-2", "Org Two")]
    )
    resolved = manager.get_clients_by_org_id("uuid-2")
    assert [c.org_name for c in resolved] == ["Org Two"]
    assert manager.get_clients_by_org_id("missing") == []


@pytest.mark.asyncio
async def test_get_clients_by_org_name_is_case_insensitive() -> None:
    manager = await _build_enriched_manager([("uuid-1", "DPN | Port")])
    resolved = manager.get_clients_by_org_name("dpn | port")
    assert [c.org_name for c in resolved] == ["DPN | Port"]


@pytest.mark.asyncio
async def test_get_clients_by_org_name_returns_all_candidates_for_shared_name() -> None:
    manager = await _build_enriched_manager(
        [("uuid-1", "Shared Name"), ("uuid-2", "Shared Name")]
    )
    candidates = manager.get_clients_by_org_name("Shared Name")
    assert {c.dd_api_key for c in candidates} == {"api-0", "api-1"}
    assert manager.get_clients_by_org_name("missing") == []
