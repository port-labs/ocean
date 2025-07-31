from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from client import ArgocdClient, ObjectKind


@pytest.fixture
def mock_argocd_client() -> ArgocdClient:
    return ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=True,
        allow_insecure=True,
    )


@pytest.mark.asyncio
async def test_get_resources(mock_argocd_client: ArgocdClient) -> None:
    kinds = [ObjectKind.CLUSTER, ObjectKind.PROJECT, ObjectKind.APPLICATION]

    for kind in kinds:
        response_data = {}
        if kind == ObjectKind.CLUSTER:
            response_data = {
                "items": [
                    {
                        "server": "test-server",
                        "name": "test-cluster",
                        "connectionState": {"status": "Successful"},
                    }
                ]
            }
        elif kind == ObjectKind.PROJECT:
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
            mock_argocd_client, "_send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = response_data
            resources = await mock_argocd_client.get_resources(resource_kind=kind)

            assert resources == response_data["items"]
            mock_request.assert_called_with(url=f"{mock_argocd_client.api_url}/{kind}s")


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
        mock_argocd_client, "get_resources", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = response_data["items"]
        kind = ObjectKind.APPLICATION
        all_history = await mock_argocd_client.get_deployment_history()
        assert len(all_history) == 1
        mock_request.assert_called_with(resource_kind=kind)


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
        mock_argocd_client, "get_resources", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = response_data["items"]
        kind = ObjectKind.APPLICATION
        all_history = await mock_argocd_client.get_deployment_history()
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
        mock_argocd_client, "get_resources", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = response_data["items"]
        kind = ObjectKind.APPLICATION
        resources = await mock_argocd_client.get_kubernetes_resource()
        assert len(resources) == 1
        mock_request.assert_called_with(resource_kind=kind)


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
        mock_argocd_client, "get_resources", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = response_data["items"]
        resources = await mock_argocd_client.get_kubernetes_resource()
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
            resources = await mock_argocd_client.get_managed_resources(application)
            assert resources == [
                {
                    **resource,
                    "__application": application,
                }
                for resource in response_data["items"]
                if resource
            ]

            application_name = application["metadata"]["name"]
            mock_request.assert_called_with(
                url=f"{mock_argocd_client.api_url}/{ObjectKind.APPLICATION}s/{application_name}/managed-resources"
            )
