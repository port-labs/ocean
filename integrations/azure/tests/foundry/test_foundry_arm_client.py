from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_integration.foundry.clients.foundry_arm_client import FoundryArmClient
from azure_integration.foundry.core.exporters.project_exporter import ProjectExporter

_ARM_ID = (
    "/subscriptions/sub-1/resourceGroups/rg-1/providers/"
    "Microsoft.CognitiveServices/accounts/acct-1/projects/proj-1"
)


@pytest.mark.asyncio
async def test_upsert_project_connection_uses_arm_id_without_discovery() -> None:
    client = FoundryArmClient()
    response = MagicMock()
    response.raise_for_status = MagicMock()
    client._http.put = AsyncMock(return_value=response)

    with (
        patch.object(ProjectExporter, "find_by_endpoint", AsyncMock()) as find_ep,
        patch(
            "azure_integration.foundry.clients.foundry_arm_client.management_headers",
            AsyncMock(return_value={}),
        ),
    ):
        await client.upsert_project_connection(
            project_endpoint="https://ignored/api/projects/p",
            name="port-conn",
            target="https://mcp",
            access_token="tok",
            project_arm_id=_ARM_ID,
        )
        find_ep.assert_not_awaited()

    put_url = client._http.put.await_args.args[0]
    assert "acct-1/projects/proj-1/connections/port-conn" in put_url
