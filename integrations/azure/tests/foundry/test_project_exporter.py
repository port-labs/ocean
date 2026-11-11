from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.core.exceptions import HttpResponseError

from azure_integration.foundry.core.exporters.project_exporter import (
    ProjectExporter,
    foundry_project_from_arm,
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
