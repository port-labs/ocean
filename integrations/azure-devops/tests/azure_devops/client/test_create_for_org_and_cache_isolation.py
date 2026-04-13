import json
from typing import Any, Generator

import pytest

from port_ocean.context.event import _event_context_stack, EventContext
from port_ocean.context.ocean import ocean

from azure_devops.client.azure_devops_client import AzureDevopsClient


@pytest.fixture
def event_context() -> Generator[None, None, None]:
    ctx = EventContext(event_type="TEST", attributes={})
    _event_context_stack.push(ctx)
    yield
    _event_context_stack.pop()


@pytest.fixture
def set_multi_org_mapping() -> Generator[dict[str, str], None, None]:
    mapping = {
        "https://dev.azure.com/org-alpha": "pat-alpha",
        "https://dev.azure.com/org-beta": "pat-beta",
    }
    previous: dict[str, Any] = {
        "organization_url": ocean.integration_config.get("organization_url"),
        "personal_access_token": ocean.integration_config.get("personal_access_token"),
        "organization_token_mapping": ocean.integration_config.get(
            "organization_token_mapping"
        ),
    }
    ocean.integration_config["organization_url"] = None
    ocean.integration_config["personal_access_token"] = None
    ocean.integration_config["organization_token_mapping"] = json.dumps(mapping)
    yield mapping
    for key, value in previous.items():
        ocean.integration_config[key] = value


def test_create_for_org_returns_matching_client(
    set_multi_org_mapping: dict[str, str], event_context: None
) -> None:
    client = AzureDevopsClient.create_for_org("https://dev.azure.com/org-alpha")
    assert isinstance(client, AzureDevopsClient)
    assert client.organization_url == "https://dev.azure.com/org-alpha"


def test_create_for_org_normalizes_trailing_slash(
    set_multi_org_mapping: dict[str, str], event_context: None
) -> None:
    client = AzureDevopsClient.create_for_org("https://dev.azure.com/org-alpha/")
    assert client.organization_url == "https://dev.azure.com/org-alpha"


def test_create_for_org_unknown_url_raises(
    set_multi_org_mapping: dict[str, str], event_context: None
) -> None:
    with pytest.raises(ValueError, match="No client configured for organization"):
        AzureDevopsClient.create_for_org("https://dev.azure.com/unknown-org")
