from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.core.exceptions import HttpResponseError

from azure_integration.foundry.discovery import (
    _data_plane_project_name,
    _endpoint_from_project_properties,
    clear_foundry_project_cache,
    discover_foundry_projects,
    foundry_project_from_arm,
    foundry_project_to_raw,
)


def _arm_project(
    *,
    subscription: str = "sub-1",
    rg: str = "rg-1",
    account: str = "acct",
    name: str = "demo",
    endpoint: str | None = "https://acct.services.ai.azure.com/api/projects/demo",
) -> dict[str, Any]:
    project: dict[str, Any] = {
        "id": (
            f"/subscriptions/{subscription}/resourceGroups/{rg}/providers/"
            f"Microsoft.CognitiveServices/accounts/{account}/projects/{name}"
        ),
        "name": name,
        "location": "eastus",
        "tags": {"env": "test"},
    }
    if endpoint:
        project["properties"] = {"endpoint": endpoint}
    return project


@pytest.mark.asyncio
async def test_discover_foundry_projects_across_subscriptions() -> None:
    clear_foundry_project_cache()
    project = _arm_project()

    async def fake_subs(
        *_args: Any, **_kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        yield [{"subscription_id": "sub-1"}]

    async def fake_ext(
        *_args: Any, **_kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        yield [project]

    async def fake_stream(*tasks: Any) -> AsyncIterator[list[dict[str, Any]]]:
        for task in tasks:
            async for batch in task:
                yield batch

    cred = MagicMock()
    cred.__aenter__ = AsyncMock(return_value=cred)
    cred.__aexit__ = AsyncMock(return_value=None)
    sub_client = MagicMock()
    sub_client.__aenter__ = AsyncMock(return_value=sub_client)
    sub_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "azure_integration.foundry.discovery.DefaultAzureCredential",
            return_value=cred,
        ),
        patch(
            "azure_integration.foundry.discovery.SubscriptionClient",
            return_value=sub_client,
        ),
        patch(
            "azure_integration.foundry.discovery.batch_resources_iterator",
            fake_subs,
        ),
        patch(
            "azure_integration.foundry.discovery.resource_extention_kind_iterator",
            fake_ext,
        ),
        patch(
            "azure_integration.foundry.discovery.stream_async_iterators_tasks",
            fake_stream,
        ),
    ):
        projects = await discover_foundry_projects(force_refresh=True)

    assert len(projects) == 1
    assert projects[0].project_name == "demo"
    assert (
        projects[0].endpoint == "https://acct.services.ai.azure.com/api/projects/demo"
    )
    raw = foundry_project_to_raw(projects[0])
    assert raw["__foundryProjectEndpoint"] == projects[0].endpoint
    assert raw["subscriptionId"] == "sub-1"


@pytest.mark.asyncio
async def test_discover_skips_forbidden_subscriptions() -> None:
    clear_foundry_project_cache()

    async def fake_subs(
        *_args: Any, **_kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        yield [{"subscription_id": "sub-denied"}]

    async def fake_ext(
        *_args: Any, **_kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        response = MagicMock()
        response.status_code = 403
        response.reason = "Forbidden"
        raise HttpResponseError(response=response)
        yield []  # keep this an async generator

    async def fake_stream(*tasks: Any) -> AsyncIterator[list[dict[str, Any]]]:
        for task in tasks:
            async for batch in task:
                yield batch

    cred = MagicMock()
    cred.__aenter__ = AsyncMock(return_value=cred)
    cred.__aexit__ = AsyncMock(return_value=None)
    sub_client = MagicMock()
    sub_client.__aenter__ = AsyncMock(return_value=sub_client)
    sub_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "azure_integration.foundry.discovery.DefaultAzureCredential",
            return_value=cred,
        ),
        patch(
            "azure_integration.foundry.discovery.SubscriptionClient",
            return_value=sub_client,
        ),
        patch(
            "azure_integration.foundry.discovery.batch_resources_iterator",
            fake_subs,
        ),
        patch(
            "azure_integration.foundry.discovery.resource_extention_kind_iterator",
            fake_ext,
        ),
        patch(
            "azure_integration.foundry.discovery.stream_async_iterators_tasks",
            fake_stream,
        ),
    ):
        projects = await discover_foundry_projects(force_refresh=True)

    assert projects == []


def test_data_plane_project_name_strips_account_prefix() -> None:
    assert (
        _data_plane_project_name("omby-project-resource/omby-project") == "omby-project"
    )
    assert _data_plane_project_name("demo") == "demo"


def test_endpoint_from_project_properties_normalizes_cognitiveservices_host() -> None:
    project = {
        "properties": {
            "endpoint": (
                "https://acct.cognitiveservices.azure.com/" "api/projects/my-proj"
            )
        }
    }
    assert (
        _endpoint_from_project_properties(project)
        == "https://acct.services.ai.azure.com/api/projects/my-proj"
    )


def test_project_from_arm_uses_services_ai_host_and_short_project_name() -> None:
    project = {
        "id": (
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/"
            "Microsoft.CognitiveServices/accounts/omby-project-resource/projects/omby-project"
        ),
        "name": "omby-project-resource/omby-project",
        "location": "eastus",
        "tags": {},
        "properties": {
            "endpoint": (
                "https://omby-project-resource.cognitiveservices.azure.com/"
                "api/projects/omby-project"
            )
        },
    }
    found = foundry_project_from_arm(project)
    assert found is not None
    assert (
        found.endpoint
        == "https://omby-project-resource.services.ai.azure.com/api/projects/omby-project"
    )
    assert found.project_name == "omby-project"
