from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from client import (
    ArgocdClient,
    ClusterState,
    ObjectKind,
)


@pytest.fixture
def mock_argocd_client() -> ArgocdClient:
    return ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=True,
        allow_insecure=True,
    )


@pytest.mark.asyncio
async def test_get_resources_for_available_clusters(
    mock_argocd_client: ArgocdClient,
) -> None:
    kinds = [ObjectKind.PROJECT, ObjectKind.APPLICATION]

    for kind in kinds:
        response_data = {}
        if kind == ObjectKind.PROJECT:
            response_data = {
                "items": [
                    {
                        "spec": {"destinations": [{"server": "*", "namespace": "*"}]},
                        "metadata": {"name": "test-project", "uid": "test-uid"},
                    }
                ]
            }
        elif kind == ObjectKind.APPLICATION:
            response_data = {
                "items": [
                    {
                        "spec": {
                            "destinations": [
                                {
                                    "server": "https://kubernetes.default.svc",
                                    "namespace": "default",
                                }
                            ],
                            "project": "default",
                        },
                        "metadata": {"name": "test-project", "uid": "test-uid"},
                    }
                ]
            }

        with patch.object(
            mock_argocd_client, "get_available_clusters", new_callable=AsyncMock
        ) as mock_clusters:
            mock_clusters.return_value = [
                {
                    "name": "test-cluster",
                    "connectionState": {"status": ClusterState.AVAILABLE.value},
                }
            ]
            with patch.object(
                mock_argocd_client, "_send_api_request", new_callable=AsyncMock
            ) as mock_request:
                mock_request.return_value = response_data
                resources = (
                    await mock_argocd_client.get_resources_for_available_clusters(
                        resource_kind=kind
                    )
                )
                assert resources == response_data["items"]
                mock_request.assert_called_with(
                    url=f"{mock_argocd_client.api_url}/{kind}s",
                    query_params={"cluster": "test-cluster"},
                )
            mock_clusters.assert_called_once()


@pytest.mark.asyncio
async def test_get_application_by_name(mock_argocd_client: ArgocdClient) -> None:
    application_name = "test-application"
    response_data = {
        "spec": {
            "destinations": [
                {
                    "server": "https://kubernetes.default.svc",
                    "namespace": "default",
                }
            ],
            "project": "default",
        },
        "metadata": {"name": "test-project", "uid": "test-uid"},
    }
    with patch.object(
        mock_argocd_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = response_data
        application = await mock_argocd_client.get_application_by_name(
            name=application_name
        )
        assert application == response_data


@pytest.mark.asyncio
async def test_get_deployment_history(mock_argocd_client: ArgocdClient) -> None:
    response_data = {
        "items": [
            {
                "spec": {
                    "destinations": [
                        {
                            "server": "https://kubernetes.default.svc",
                            "namespace": "default",
                        }
                    ],
                    "project": "default",
                },
                "metadata": {"name": "test-project", "uid": "test-uid"},
                "status": {
                    "history": [
                        {
                            "revision": "f58c7ed8cfe28ad70701c5923fdbd0154388ea9f",
                            "deployedAt": "2025-07-23T16:18:43Z",
                            "id": 0,
                            "source": {
                                "repoURL": "https://github.com/argoproj/argocd-example-apps.git",
                                "path": "guestbook",
                            },
                            "deployStartedAt": "2025-07-23T16:18:43Z",
                            "initiatedBy": {"username": "admin"},
                        }
                    ]
                },
            }
        ]
    }
    with patch.object(
        mock_argocd_client,
        "get_resources_for_available_clusters",
        new_callable=AsyncMock,
    ) as mock_request:
        mock_request.return_value = response_data["items"]
        kind = ObjectKind.APPLICATION
        async for all_history in mock_argocd_client.get_deployment_history():
            mock_request.assert_called_with(resource_kind=kind)
            assert len(all_history) == 1


@pytest.mark.asyncio
async def test_get_deployment_history_without_history_data(
    mock_argocd_client: ArgocdClient,
) -> None:
    response_data = {
        "items": [
            {
                "spec": {
                    "destinations": [
                        {
                            "server": "https://kubernetes.default.svc",
                            "namespace": "default",
                        }
                    ],
                    "project": "default",
                },
                "metadata": {"name": "test-project", "uid": "test-uid"},
                "status": {},
            }
        ]
    }
    with patch.object(
        mock_argocd_client,
        "get_resources_for_available_clusters",
        new_callable=AsyncMock,
    ) as mock_request:
        mock_request.return_value = response_data["items"]
        kind = ObjectKind.APPLICATION
        async for all_history in mock_argocd_client.get_deployment_history():
            assert len(all_history) == 0
            mock_request.assert_called_with(resource_kind=kind)


@pytest.mark.asyncio
async def test_get_kubernetes_resource(mock_argocd_client: ArgocdClient) -> None:
    response_data = {
        "items": [
            {
                "spec": {
                    "destinations": [
                        {
                            "server": "https://kubernetes.default.svc",
                            "namespace": "default",
                        }
                    ],
                    "project": "default",
                },
                "metadata": {"name": "test-project", "uid": "test-uid"},
                "status": {
                    "resources": [
                        {
                            "version": "v1",
                            "kind": "Service",
                            "namespace": "default",
                            "name": "guestbook-ui",
                            "status": "Synced",
                            "health": {"status": "Healthy"},
                        }
                    ]
                },
            }
        ]
    }
    with patch.object(
        mock_argocd_client,
        "get_resources_for_available_clusters",
        new_callable=AsyncMock,
    ) as mock_request:
        mock_request.return_value = response_data["items"]
        kind = ObjectKind.APPLICATION
        async for resources in mock_argocd_client.get_kubernetes_resource():
            mock_request.assert_called_with(resource_kind=kind)
            assert len(resources) == 1


@pytest.mark.asyncio
async def test_get_kubernetes_resource_without_resource_data(
    mock_argocd_client: ArgocdClient,
) -> None:
    response_data = {
        "items": [
            {
                "spec": {
                    "destinations": [
                        {
                            "server": "https://kubernetes.default.svc",
                            "namespace": "default",
                        }
                    ],
                    "project": "default",
                },
                "metadata": {"name": "test-project", "uid": "test-uid"},
                "status": {},
            }
        ]
    }
    with patch.object(
        mock_argocd_client,
        "get_resources_for_available_clusters",
        new_callable=AsyncMock,
    ) as mock_request:
        mock_request.return_value = response_data["items"]
        async for resources in mock_argocd_client.get_kubernetes_resource():
            assert len(resources) == 0
            mock_request.assert_called_with(resource_kind=ObjectKind.APPLICATION)


@pytest.mark.asyncio
async def test_get_managed_resources(
    mock_argocd_client: ArgocdClient,
) -> None:
    response_data: dict[str, Any] = {
        "items": [
            {
                "kind": "Service",
                "namespace": "default",
                "name": "test-svc-ui",
                "metadata": {"name": "test-svc", "uid": "test-uid1"},
            },
            {
                "kind": "Deployment",
                "namespace": "default",
                "name": "test-deployment",
                "metadata": {"name": "test-deployment", "uid": "test-uid2"},
            },
        ]
    }
    with patch.object(
        mock_argocd_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = response_data

        for application in response_data["items"]:
            async for resources in mock_argocd_client.get_managed_resources(
                application
            ):
                assert len(resources) == len(response_data["items"])
                application_name = application["metadata"]["name"]
                mock_request.assert_called_with(
                    url=f"{mock_argocd_client.api_url}/{ObjectKind.APPLICATION}s/{application_name}/managed-resources"
                )


@pytest.mark.asyncio
async def test_get_clusters_with_only_available_clusters(
    mock_argocd_client: ArgocdClient,
) -> None:
    """Test that get_clusters yields only available clusters."""
    response_data = {
        "items": [
            {
                "server": "https://cluster1.example.com",
                "name": "cluster-1",
                "connectionState": {"status": "Successful"},
            },
            {
                "server": "https://cluster2.example.com",
                "name": "cluster-2",
                "connectionState": {"status": "Successful"},
            },
            {
                "server": "https://cluster3.example.com",
                "name": "cluster-3",
                "connectionState": {"status": "Successful"},
            },
        ]
    }
    with patch.object(
        mock_argocd_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = response_data

        all_clusters = []
        async for cluster_batch in mock_argocd_client.get_clusters():
            all_clusters.extend(cluster_batch)

        assert len(all_clusters) == 3
        assert all(
            cluster["connectionState"]["status"] == ClusterState.AVAILABLE.value
            for cluster in all_clusters
        )
        mock_request.assert_called_with(url=f"{mock_argocd_client.api_url}/clusters")


@pytest.mark.asyncio
async def test_get_clusters_filters_unavailable_clusters(
    mock_argocd_client: ArgocdClient,
) -> None:
    """Test that get_clusters filters out unavailable clusters."""
    response_data = {
        "items": [
            {
                "server": "https://cluster1.example.com",
                "name": "cluster-1",
                "connectionState": {"status": "Successful"},
            },
            {
                "server": "https://cluster2.example.com",
                "name": "cluster-2",
                "connectionState": {"status": "Failed"},
            },
            {
                "server": "https://cluster3.example.com",
                "name": "cluster-3",
                "connectionState": {"status": "Successful"},
            },
            {
                "server": "https://cluster4.example.com",
                "name": "cluster-4",
                "connectionState": {"status": "Unknown"},
            },
            {
                "server": "https://cluster5.example.com",
                "name": "cluster-5",
                "connectionState": {"status": "Successful"},
            },
        ]
    }
    with patch.object(
        mock_argocd_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = response_data

        all_clusters = []
        async for cluster_batch in mock_argocd_client.get_clusters(
            skip_unavailable_clusters=True
        ):
            all_clusters.extend(cluster_batch)

        # Only 3 out of 5 clusters have "Successful" status
        assert len(all_clusters) == 3
        assert all(
            cluster["connectionState"]["status"] == ClusterState.AVAILABLE.value
            for cluster in all_clusters
        )
        # Verify the correct clusters were included
        cluster_names = [cluster["name"] for cluster in all_clusters]
        assert cluster_names == ["cluster-1", "cluster-3", "cluster-5"]
        mock_request.assert_called_with(url=f"{mock_argocd_client.api_url}/clusters")
