from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_integration.foundry.discovery import (
    _data_plane_project_name,
    _endpoint_from_project_properties,
    _project_from_arm,
    clear_foundry_project_cache,
    discover_foundry_projects,
    foundry_project_to_raw,
)


@pytest.mark.asyncio
async def test_discover_foundry_projects_across_subscriptions() -> None:
    clear_foundry_project_cache()

    account = {
        "id": (
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/"
            "Microsoft.CognitiveServices/accounts/acct"
        ),
        "name": "acct",
        "location": "eastus",
        "properties": {"customSubDomainName": "acct"},
        "tags": {},
    }
    project = {
        "id": f"{account['id']}/projects/demo",
        "name": "demo",
        "location": "eastus",
        "tags": {"env": "test"},
    }

    http = MagicMock()
    http.get = AsyncMock(
        side_effect=[
            MagicMock(
                status_code=200,
                json=lambda: {
                    "value": [{"subscriptionId": "sub-1", "state": "Enabled"}]
                },
                raise_for_status=lambda: None,
            ),
            MagicMock(
                status_code=200,
                json=lambda: {"value": [account]},
                raise_for_status=lambda: None,
            ),
            MagicMock(
                status_code=200,
                json=lambda: {"value": [project]},
                raise_for_status=lambda: None,
            ),
        ]
    )
    http.aclose = AsyncMock()

    with (
        patch(
            "azure_integration.foundry.discovery.OceanAsyncClient",
            return_value=http,
        ),
        patch(
            "azure_integration.foundry.discovery._management_headers",
            AsyncMock(return_value={"Authorization": "Bearer x"}),
        ),
    ):
        projects = await discover_foundry_projects(force_refresh=True)

    assert len(projects) == 1
    assert projects[0].project_name == "demo"
    assert (
        projects[0].endpoint
        == "https://acct.services.ai.azure.com/api/projects/demo"
    )
    raw = foundry_project_to_raw(projects[0])
    assert raw["__foundryProjectEndpoint"] == projects[0].endpoint
    assert raw["subscriptionId"] == "sub-1"


@pytest.mark.asyncio
async def test_discover_skips_forbidden_subscriptions() -> None:
    clear_foundry_project_cache()
    http = MagicMock()
    forbidden = MagicMock(status_code=403)
    forbidden.raise_for_status = MagicMock()
    http.get = AsyncMock(
        side_effect=[
            MagicMock(
                status_code=200,
                json=lambda: {
                    "value": [{"subscriptionId": "sub-denied", "state": "Enabled"}]
                },
                raise_for_status=lambda: None,
            ),
            forbidden,
        ]
    )
    http.aclose = AsyncMock()

    with (
        patch(
            "azure_integration.foundry.discovery.OceanAsyncClient",
            return_value=http,
        ),
        patch(
            "azure_integration.foundry.discovery._management_headers",
            AsyncMock(return_value={"Authorization": "Bearer x"}),
        ),
    ):
        projects = await discover_foundry_projects(force_refresh=True)

    assert projects == []


def test_data_plane_project_name_strips_account_prefix() -> None:
    assert _data_plane_project_name("omby-project-resource/omby-project") == "omby-project"
    assert _data_plane_project_name("demo") == "demo"


def test_endpoint_from_project_properties_normalizes_cognitiveservices_host() -> None:
    project = {
        "properties": {
            "endpoint": (
                "https://acct.cognitiveservices.azure.com/"
                "api/projects/my-proj"
            )
        }
    }
    assert (
        _endpoint_from_project_properties(project)
        == "https://acct.services.ai.azure.com/api/projects/my-proj"
    )


def test_project_from_arm_uses_services_ai_host_and_short_project_name() -> None:
    account = {
        "id": (
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/"
            "Microsoft.CognitiveServices/accounts/omby-project-resource"
        ),
        "name": "omby-project-resource",
        "location": "eastus",
        "properties": {
            "customSubDomainName": "omby-project-resource",
            "endpoint": "https://omby-project-resource.cognitiveservices.azure.com/",
        },
        "tags": {},
    }
    project = {
        "id": f"{account['id']}/projects/omby-project",
        "name": "omby-project-resource/omby-project",
        "location": "eastus",
        "tags": {},
    }
    found = _project_from_arm(account, project)
    assert found is not None
    assert (
        found.endpoint
        == "https://omby-project-resource.services.ai.azure.com/api/projects/omby-project"
    )
    assert found.project_name == "omby-project"
