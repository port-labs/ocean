from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.core.exceptions import HttpResponseError

from azure_integration.foundry.core.exporters.project_exporter import (
    FoundryProject,
    ProjectExporter,
    foundry_project_from_arm,
    foundry_project_from_arm_id,
)

_MODULE = "azure_integration.foundry.core.exporters.project_exporter"


def _arm_project(
    *,
    subscription: str = "sub-1",
    rg: str = "rg-1",
    account: str = "acct",
    name: str = "demo",
) -> dict[str, Any]:
    return {
        "id": (
            f"/subscriptions/{subscription}/resourceGroups/{rg}/providers/"
            f"Microsoft.CognitiveServices/accounts/{account}/projects/{name}"
        ),
        "name": name,
        "location": "eastus",
        "tags": {"env": "test"},
    }


def _credential_and_sub_client() -> tuple[MagicMock, MagicMock]:
    cred = MagicMock()
    cred.__aenter__ = AsyncMock(return_value=cred)
    cred.__aexit__ = AsyncMock(return_value=None)
    sub_client = MagicMock()
    sub_client.__aenter__ = AsyncMock(return_value=sub_client)
    sub_client.__aexit__ = AsyncMock(return_value=None)
    return cred, sub_client


@pytest.mark.asyncio
async def test_project_exporter_across_subscriptions() -> None:
    project = _arm_project()
    seen_api_versions: list[str] = []

    async def fake_subs(
        *_args: Any, **_kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        yield [{"subscription_id": "sub-1"}]

    async def fake_ext(
        *_args: Any, **_kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        seen_api_versions.append(_kwargs["api_version"])
        yield [project]

    cred, sub_client = _credential_and_sub_client()

    with (
        patch(f"{_MODULE}.DefaultAzureCredential", return_value=cred),
        patch(f"{_MODULE}.SubscriptionClient", return_value=sub_client),
        patch(f"{_MODULE}.batch_resources_iterator", fake_subs),
        patch(f"{_MODULE}.resource_extention_kind_iterator", fake_ext),
    ):
        projects: list[dict[str, Any]] = []
        async for batch in ProjectExporter().get_paginated_resources(
            api_version="2024-10-01"
        ):
            projects.extend(batch)

    assert seen_api_versions == ["2024-10-01"]
    assert len(projects) == 1
    assert projects[0]["name"] == "demo"
    assert (
        projects[0]["__foundryProjectEndpoint"]
        == "https://acct.services.ai.azure.com/api/projects/demo"
    )
    assert projects[0]["subscriptionId"] == "sub-1"
    assert projects[0]["id"].endswith("/projects/demo")
    assert projects[0]["type"] == "Microsoft.CognitiveServices/accounts/projects"


@pytest.mark.asyncio
async def test_project_exporter_yields_successes_then_raises_failed_subscriptions() -> (
    None
):
    ok_project = _arm_project(subscription="sub-ok", account="ok-acct", name="ok")

    async def fake_subs(
        *_args: Any, **_kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        yield [
            {"subscription_id": "sub-ok"},
            {"subscription_id": "sub-denied"},
        ]

    async def fake_ext(
        *_args: Any, subscription_id: str, **_kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        if subscription_id == "sub-denied":
            response = MagicMock()
            response.status_code = 403
            response.reason = "Forbidden"
            raise HttpResponseError(response=response)
            yield []  # keep this an async generator
        yield [ok_project]

    cred, sub_client = _credential_and_sub_client()

    with (
        patch(f"{_MODULE}.DefaultAzureCredential", return_value=cred),
        patch(f"{_MODULE}.SubscriptionClient", return_value=sub_client),
        patch(f"{_MODULE}.batch_resources_iterator", fake_subs),
        patch(f"{_MODULE}.resource_extention_kind_iterator", fake_ext),
    ):
        projects: list[dict[str, Any]] = []
        with pytest.raises(ExceptionGroup) as exc_info:  # noqa: F821
            async for batch in ProjectExporter().get_paginated_resources():
                projects.extend(batch)

    assert len(projects) == 1
    assert projects[0]["name"] == "ok"
    assert "Foundry project exporter failed with 1 error(s)" in str(exc_info.value)
    assert isinstance(exc_info.value.exceptions[0], HttpResponseError)


@pytest.mark.asyncio
async def test_project_exporter_filters_regions() -> None:
    east = _arm_project(account="east-acct", name="east")
    west = _arm_project(account="west-acct", name="west")
    west["location"] = "westus"

    async def fake_subs(
        *_args: Any, **_kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        yield [{"subscription_id": "sub-1"}]

    async def fake_ext(
        *_args: Any, **_kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        yield [east, west]

    cred, sub_client = _credential_and_sub_client()

    with (
        patch(f"{_MODULE}.DefaultAzureCredential", return_value=cred),
        patch(f"{_MODULE}.SubscriptionClient", return_value=sub_client),
        patch(f"{_MODULE}.batch_resources_iterator", fake_subs),
        patch(f"{_MODULE}.resource_extention_kind_iterator", fake_ext),
    ):
        exporter = ProjectExporter()
        east_only: list[dict[str, Any]] = []
        async for batch in exporter.get_paginated_resources(
            api_version="2024-10-01", regions=["EastUS"]
        ):
            east_only.extend(batch)
        all_projects: list[dict[str, Any]] = []
        async for batch in exporter.get_paginated_resources(api_version="2024-10-01"):
            all_projects.extend(batch)

    assert [p["name"] for p in east_only] == ["east"]
    assert [p["name"] for p in all_projects] == ["east", "west"]


def test_project_from_arm_builds_endpoint_from_arm_id() -> None:
    project = {
        "id": (
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/"
            "Microsoft.CognitiveServices/accounts/omby-project-resource/projects/omby-project"
        ),
        "name": "omby-project-resource/omby-project",
        "location": "eastus",
        "tags": {},
    }
    found = foundry_project_from_arm(project)
    assert found is not None
    assert (
        found.endpoint
        == "https://omby-project-resource.services.ai.azure.com/api/projects/omby-project"
    )
    assert found.project_name == "omby-project"


def test_foundry_project_from_arm_id() -> None:
    arm_id = (
        "/subscriptions/sub-1/resourceGroups/rg-1/providers/"
        "Microsoft.CognitiveServices/accounts/acct-1/projects/proj-1"
    )
    project = foundry_project_from_arm_id(arm_id)
    assert project is not None
    assert project.subscription_id == "sub-1"
    assert project.project_name == "proj-1"
    assert (
        project.endpoint
        == "https://acct-1.services.ai.azure.com/api/projects/proj-1"
    )
    assert foundry_project_from_arm_id("not-an-arm-id") is None


async def _find_by_endpoint_with_projects(
    endpoint: str, projects: list[FoundryProject]
) -> FoundryProject:
    async def fake_pages(
        *_args: Any, **_kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        yield [project.model_dump(by_alias=True) for project in projects]

    exporter = ProjectExporter()
    with patch.object(exporter, "get_paginated_resources", fake_pages):
        return await exporter.find_by_endpoint(endpoint)


@pytest.mark.asyncio
async def test_find_by_endpoint_resolves_default_project_alias() -> None:
    project = foundry_project_from_arm(_arm_project(account="acct", name="demo"))
    assert project is not None
    found = await _find_by_endpoint_with_projects(
        "https://acct.services.ai.azure.com/api/projects/_project",
        [project],
    )
    assert found.project_name == "demo"
    assert found.account_name == "acct"


@pytest.mark.asyncio
async def test_find_by_endpoint_rejects_ambiguous_default_alias() -> None:
    first = foundry_project_from_arm(_arm_project(account="acct", name="one"))
    second = foundry_project_from_arm(_arm_project(account="acct", name="two"))
    assert first is not None and second is not None
    with pytest.raises(ValueError, match="ambiguous"):
        await _find_by_endpoint_with_projects(
            "https://acct.services.ai.azure.com/api/projects/_project",
            [first, second],
        )
