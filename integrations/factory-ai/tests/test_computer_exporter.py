from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from factory_ai.core.exporters.computer import ComputerExporter
from factory_ai.core.exporters.computer.models import (
    Computer,
    GetComputerOptions,
    ListComputerOptions,
    ListComputersResponse,
)

_MIN_COMPUTER = {
    "id": "comp-1",
    "name": "droid-box",
    "providerType": "e2b",
    "createdAt": 1_700_000_000_000,
    "status": "active",
    "isListed": True,
    "providerStatus": "running",
    "computerSource": {
        "kind": "environment",
        "environmentId": "env-1",
    },
}


@pytest.mark.asyncio
async def test_computer_exporter_lists_via_typed_response() -> None:
    client_mock = MagicMock()
    response = ListComputersResponse.parse_obj({"computers": [_MIN_COMPUTER]})
    client_mock.get = AsyncMock(return_value=response)
    exporter = ComputerExporter(client_mock)

    batches = [
        batch async for batch in exporter.get_paginated_resources(ListComputerOptions())
    ]

    assert len(batches) == 1
    assert batches[0][0]["id"] == "comp-1"
    assert batches[0][0]["providerType"] == "e2b"
    assert batches[0][0]["computerSource"]["environmentId"] == "env-1"
    client_mock.get.assert_awaited_once_with(
        "/api/v0/computers",
        ListComputersResponse,
        params=None,
    )


@pytest.mark.asyncio
async def test_computer_exporter_forwards_list_query_params() -> None:
    client_mock = MagicMock()
    client_mock.get = AsyncMock(
        return_value=ListComputersResponse.parse_obj({"computers": []})
    )
    exporter = ComputerExporter(client_mock)
    options = ListComputerOptions(
        service_account_id="sa-9",
        host_id="11111111-1111-1111-1111-111111111111",
        include_provisioning_steps=True,
        include_unlisted=True,
    )

    [batch async for batch in exporter.get_paginated_resources(options)]

    client_mock.get.assert_awaited_once_with(
        "/api/v0/computers",
        ListComputersResponse,
        params={
            "serviceAccountId": "sa-9",
            "hostId": "11111111-1111-1111-1111-111111111111",
            "includeProvisioningSteps": "true",
            "includeUnlisted": "true",
        },
    )


@pytest.mark.asyncio
async def test_computer_exporter_get_resource() -> None:
    client_mock = MagicMock()
    client_mock.get_or_none = AsyncMock(return_value=Computer.parse_obj(_MIN_COMPUTER))
    exporter = ComputerExporter(client_mock)

    result = await exporter.get_resource(GetComputerOptions(computer_id="comp-1"))

    assert result is not None
    assert result["id"] == "comp-1"
    assert result["name"] == "droid-box"
    client_mock.get_or_none.assert_awaited_once_with(
        "/api/v0/computers/comp-1",
        Computer,
    )


@pytest.mark.asyncio
async def test_computer_exporter_get_resource_not_found() -> None:
    client_mock = MagicMock()
    client_mock.get_or_none = AsyncMock(return_value=None)
    exporter = ComputerExporter(client_mock)

    result = await exporter.get_resource(GetComputerOptions(computer_id="missing"))

    assert result is None
