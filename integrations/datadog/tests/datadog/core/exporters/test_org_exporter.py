from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from datadog.client import DatadogClient
from datadog.core.exporters import OrgExporter
from datadog.core.exporters.org_exporter import GetOrgOptions


@pytest.mark.asyncio
async def test_get_orgs(mock_datadog_client: DatadogClient) -> None:
    orgs_response: dict[str, list[dict[str, Any]]] = {
        "orgs": [
            {"public_id": "org1", "name": "Org One"},
            {"public_id": "org2", "name": "Org Two"},
        ]
    }

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = orgs_response

        exporter = OrgExporter(mock_datadog_client)
        orgs = []
        async for org_batch in exporter.get_paginated_resources():
            orgs.extend(org_batch)

        assert orgs == orgs_response["orgs"]
        # Single, non-paginated request to the v1 list endpoint.
        mock_request.assert_called_once_with(
            f"{mock_datadog_client.api_url}/api/v1/org"
        )


@pytest.mark.asyncio
async def test_get_orgs_empty(mock_datadog_client: DatadogClient) -> None:
    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {"orgs": []}

        exporter = OrgExporter(mock_datadog_client)
        batches = [batch async for batch in exporter.get_paginated_resources()]

        # An empty list yields nothing rather than an empty batch.
        assert batches == []


@pytest.mark.asyncio
async def test_get_orgs_missing_key(mock_datadog_client: DatadogClient) -> None:
    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {}

        exporter = OrgExporter(mock_datadog_client)
        batches = [batch async for batch in exporter.get_paginated_resources()]

        assert batches == []


@pytest.mark.asyncio
async def test_get_resource(mock_datadog_client: DatadogClient) -> None:
    org = {"public_id": "org1", "name": "Org One"}

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {"org": org}

        exporter = OrgExporter(mock_datadog_client)
        result = await exporter.get_resource(GetOrgOptions(resource_id="org1"))

        assert result == org
        mock_request.assert_called_once_with(
            f"{mock_datadog_client.api_url}/api/v1/org/org1"
        )


@pytest.mark.asyncio
async def test_get_resource_missing_key(mock_datadog_client: DatadogClient) -> None:
    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {}

        exporter = OrgExporter(mock_datadog_client)
        result = await exporter.get_resource(GetOrgOptions(resource_id="org1"))

        assert result is None
