from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from factory_ai.core.exporters.environment import EnvironmentExporter
from factory_ai.core.exporters.environment.models import (
    Environment,
    GetEnvironmentOptions,
    ListEnvironmentOptions,
    ListEnvironmentsResponse,
)

_MIN_ENVIRONMENT = {
    "id": "env-1",
    "name": "Default",
    "repositories": [{"url": "https://github.com/acme/app", "script": ""}],
    "source": {
        "id": "src-1",
        "name": "Ubuntu",
        "supportsRepositories": True,
        "supportsSetupScripts": True,
        "provider": {"id": "prov-1", "name": "Factory"},
    },
    "createdAt": 1_700_000_000_000,
    "updatedAt": 1_700_000_100_000,
    "status": "ready",
    "isDefault": True,
}


@pytest.mark.asyncio
async def test_environment_exporter_lists_via_typed_response() -> None:
    client_mock = MagicMock()
    response = ListEnvironmentsResponse.model_validate(
        {"environments": [_MIN_ENVIRONMENT]}
    )
    client_mock.get = AsyncMock(return_value=response)
    exporter = EnvironmentExporter(client_mock)

    batches = [
        batch
        async for batch in exporter.get_paginated_resources(ListEnvironmentOptions())
    ]

    assert len(batches) == 1
    assert batches[0][0]["id"] == "env-1"
    assert batches[0][0]["isDefault"] is True
    assert batches[0][0]["source"]["provider"]["name"] == "Factory"
    client_mock.get.assert_awaited_once_with(
        "/api/v0/environments",
        ListEnvironmentsResponse,
        params=None,
    )


@pytest.mark.asyncio
async def test_environment_exporter_forwards_service_account_id() -> None:
    client_mock = MagicMock()
    client_mock.get = AsyncMock(
        return_value=ListEnvironmentsResponse.model_validate({"environments": []})
    )
    exporter = EnvironmentExporter(client_mock)
    options = ListEnvironmentOptions(service_account_id="sa-9")

    [batch async for batch in exporter.get_paginated_resources(options)]

    client_mock.get.assert_awaited_once_with(
        "/api/v0/environments",
        ListEnvironmentsResponse,
        params={"serviceAccountId": "sa-9"},
    )


@pytest.mark.asyncio
async def test_environment_exporter_get_resource() -> None:
    client_mock = MagicMock()
    client_mock.get_or_none = AsyncMock(
        return_value=Environment.model_validate(_MIN_ENVIRONMENT)
    )
    exporter = EnvironmentExporter(client_mock)

    result = await exporter.get_resource(GetEnvironmentOptions(environment_id="env-1"))

    assert result is not None
    assert result["id"] == "env-1"
    assert result["name"] == "Default"
    client_mock.get_or_none.assert_awaited_once_with(
        "/api/v0/environments/env-1",
        Environment,
    )
