from unittest.mock import AsyncMock, patch

import pytest
from client import ArgocdClient, ObjectKind


@pytest.fixture(autouse=True)
def mock_argocd_client() -> ArgocdClient:
    ArgocdClient(
        token="test_token",
        server_url="test_server_url",
        ignore_server_error=False,
        allow_insecure=True,
    )


@pytest.mark.asyncio
async def test_get_resources(mock_argocd_client: ArgocdClient) -> None:
    kinds = [ObjectKind.CLUSTER, ObjectKind.PROJECT, ObjectKind.APPLICATION]
    for kind in kinds:
        response_data = {"metadata": {"resourceVersion": "614680"}, "items": []}

        with patch.object(
            mock_argocd_client, "_send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = response_data

        resources = []
        async for resource in mock_argocd_client.get_resources(resource_kind=kind):
            resources.extend(resource)

        assert resources == response_data["items"]
        mock_request.assert_called_with(f"{mock_argocd_client.api_url}/{kind}s")
