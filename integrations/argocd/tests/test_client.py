import asyncio
import json
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from client import (
    ArgocdClient,
    ClusterState,
    MAXIMUM_CONCURRENT_CLUSTER_REQUESTS,
    ObjectKind,
)


@pytest.fixture
def mock_argocd_client() -> ArgocdClient:
    return ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=True,
        allow_insecure=True,
        use_streaming=True,
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

            async def mock_stream_json(*args: Any, **kwargs: Any) -> Any:
                yield response_data["items"]

            with patch.object(
                mock_argocd_client.streaming_client,
                "stream_json",
                side_effect=mock_stream_json,
            ) as mock_stream:
                resources = []
                async for (
                    resource_batch
                ) in mock_argocd_client.get_resources_for_available_clusters(
                    resource_kind=kind
                ):
                    resources.extend(resource_batch)

                assert resources == response_data["items"]
                mock_stream.assert_called_with(
                    url=f"{mock_argocd_client.api_url}/{kind}s",
                    target_items_path="items",
                    params={"selector": "cluster=test-cluster"},
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
        mock_request.assert_called_once_with(
            url=f"{mock_argocd_client.api_url}/{ObjectKind.APPLICATION}s/{application_name}",
            query_params={},
        )


@pytest.mark.asyncio
async def test_get_application_by_name_with_namespace(
    mock_argocd_client: ArgocdClient,
) -> None:
    application_name = "test-application"
    application_namespace = "test-namespace"
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
            name=application_name,
            namespace=application_namespace,
        )
        assert application == response_data
        mock_request.assert_called_once_with(
            url=f"{mock_argocd_client.api_url}/{ObjectKind.APPLICATION}s/{application_name}",
            query_params={"appNamespace": application_namespace},
        )


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

    async def mock_resources_generator(*args: Any, **kwargs: Any) -> Any:
        yield response_data["items"]

    with patch(
        "client.ArgocdClient.get_resources_for_available_clusters",
        side_effect=mock_resources_generator,
    ) as mock_request:
        kind = ObjectKind.APPLICATION
        async for all_history in mock_argocd_client.get_deployment_history():
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

    async def mock_resources_generator(*args: Any, **kwargs: Any) -> Any:
        yield response_data["items"]

    with patch(
        "client.ArgocdClient.get_resources_for_available_clusters",
        side_effect=mock_resources_generator,
    ) as mock_request:
        kind = ObjectKind.APPLICATION
        histories = [
            history async for history in mock_argocd_client.get_deployment_history()
        ]
        assert not histories
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

    async def mock_resources_generator(*args: Any, **kwargs: Any) -> Any:
        yield response_data["items"]

    with patch(
        "client.ArgocdClient.get_resources_for_available_clusters",
        side_effect=mock_resources_generator,
    ) as mock_request:
        kind = ObjectKind.APPLICATION
        async for resources in mock_argocd_client.get_kubernetes_resource():
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

    async def mock_resources_generator(*args: Any, **kwargs: Any) -> Any:
        yield response_data["items"]

    with patch(
        "client.ArgocdClient.get_resources_for_available_clusters",
        side_effect=mock_resources_generator,
    ) as mock_request:
        resources_list = [
            res async for res in mock_argocd_client.get_kubernetes_resource()
        ]
        assert not resources_list
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

    async def mock_stream_json(*args: Any, **kwargs: Any) -> Any:
        yield response_data["items"]

    with patch.object(
        mock_argocd_client.streaming_client,
        "stream_json",
        side_effect=mock_stream_json,
    ) as mock_stream:
        for application in response_data["items"]:
            async for resources in mock_argocd_client.get_managed_resources(
                application
            ):
                assert len(resources) == len(response_data["items"])
                application_name = application["metadata"]["name"]
                mock_stream.assert_called_with(
                    url=f"{mock_argocd_client.api_url}/{ObjectKind.APPLICATION}s/{application_name}/managed-resources",
                    target_items_path="items",
                    params=None,
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

    async def mock_stream_json(*args: Any, **kwargs: Any) -> Any:
        yield response_data["items"]

    with patch.object(
        mock_argocd_client.streaming_client,
        "stream_json",
        side_effect=mock_stream_json,
    ) as mock_stream:
        all_clusters = []
        async for cluster_batch in mock_argocd_client.get_clusters():
            all_clusters.extend(cluster_batch)

        assert len(all_clusters) == 3
        assert all(
            cluster["connectionState"]["status"] == ClusterState.AVAILABLE.value
            for cluster in all_clusters
        )
        mock_stream.assert_called_with(
            url=f"{mock_argocd_client.api_url}/clusters",
            target_items_path="items",
            params=None,
        )


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

        async def mock_stream_json(*args: Any, **kwargs: Any) -> Any:
            yield response_data["items"]

        with patch.object(
            mock_argocd_client.streaming_client,
            "stream_json",
            side_effect=mock_stream_json,
        ) as mock_stream:
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
            mock_stream.assert_called_with(
                url=f"{mock_argocd_client.api_url}/clusters",
                target_items_path="items",
                params=None,
            )


# Tests for streaming vs non-streaming functionality


@pytest.mark.asyncio
async def test_get_clusters_with_streaming_enabled() -> None:
    """Test get_clusters uses streaming when enabled"""
    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=False,
        allow_insecure=True,
        use_streaming=True,
    )

    response_data = {
        "items": [
            {"name": "cluster-1", "connectionState": {"status": "Successful"}},
            {"name": "cluster-2", "connectionState": {"status": "Failed"}},
        ]
    }

    async def mock_stream_json(*args: Any, **kwargs: Any) -> Any:
        yield response_data["items"]

    with patch.object(
        client.streaming_client, "stream_json", side_effect=mock_stream_json
    ) as mock_stream:
        with patch.object(client, "_send_api_request") as mock_request:
            clusters = []
            async for cluster_batch in client.get_clusters():
                clusters.extend(cluster_batch)

            # Should use streaming, not direct API request
            mock_stream.assert_called_once()
            mock_request.assert_not_called()
            assert len(clusters) == 2


@pytest.mark.asyncio
async def test_get_clusters_with_streaming_disabled() -> None:
    """Test get_clusters uses direct API requests when streaming disabled"""
    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=False,
        allow_insecure=True,
        use_streaming=False,
    )

    response_data = {
        "items": [
            {"name": "cluster-1", "connectionState": {"status": "Successful"}},
            {"name": "cluster-2", "connectionState": {"status": "Failed"}},
        ]
    }

    with patch.object(client.streaming_client, "stream_json") as mock_stream:
        with patch.object(
            client,
            "_send_api_request",
            new_callable=AsyncMock,
            return_value=response_data,
        ) as mock_request:
            clusters = []
            async for cluster_batch in client.get_clusters():
                clusters.extend(cluster_batch)

            # Should use direct API request, not streaming
            mock_request.assert_called_once()
            mock_stream.assert_not_called()
            assert len(clusters) == 2


@pytest.mark.asyncio
async def test_get_clusters_skip_unavailable_with_streaming_disabled() -> None:
    """Test get_clusters filters unavailable clusters when streaming disabled"""
    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=False,
        allow_insecure=True,
        use_streaming=False,
    )

    response_data = {
        "items": [
            {"name": "cluster-1", "connectionState": {"status": "Successful"}},
            {"name": "cluster-2", "connectionState": {"status": "Failed"}},
            {"name": "cluster-3", "connectionState": {"status": "Successful"}},
        ]
    }

    with patch.object(
        client, "_send_api_request", new_callable=AsyncMock, return_value=response_data
    ):
        clusters = []
        async for cluster_batch in client.get_clusters(skip_unavailable_clusters=True):
            clusters.extend(cluster_batch)

        # Should only have successful clusters
        assert len(clusters) == 2
        assert all(c["connectionState"]["status"] == "Successful" for c in clusters)


@pytest.mark.asyncio
async def test_get_resources_for_available_clusters_with_streaming_disabled() -> None:
    """Test get_resources_for_available_clusters uses direct API requests when streaming disabled"""
    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=False,
        allow_insecure=True,
        use_streaming=False,
    )

    # Mock available clusters
    with patch.object(
        client, "get_available_clusters", new_callable=AsyncMock
    ) as mock_clusters:
        mock_clusters.return_value = [{"name": "test-cluster"}]

        response_data = {
            "items": [
                {"name": "app1", "metadata": {"uid": "uid1"}},
                {"name": "app2", "metadata": {"uid": "uid2"}},
            ]
        }

        with patch.object(client.streaming_client, "stream_json") as mock_stream:
            with patch.object(
                client,
                "_send_api_request",
                new_callable=AsyncMock,
                return_value=response_data,
            ) as mock_request:
                resources = []
                async for resource_batch in client.get_resources_for_available_clusters(
                    ObjectKind.APPLICATION
                ):
                    resources.extend(resource_batch)

                # Should use direct API request, not streaming
                mock_request.assert_called_once_with(
                    url=f"{client.api_url}/applications",
                    query_params={"selector": "cluster=test-cluster"},
                )
                mock_stream.assert_not_called()
                assert len(resources) == 2


@pytest.mark.asyncio
async def test_get_managed_resources_with_streaming_disabled() -> None:
    """Test get_managed_resources uses direct API requests when streaming disabled"""
    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=False,
        allow_insecure=True,
        use_streaming=False,
    )

    application = {"metadata": {"name": "test-app"}}
    response_data = {
        "items": [
            {"kind": "Service", "name": "svc1"},
            {"kind": "Deployment", "name": "deploy1"},
        ]
    }

    with patch.object(client.streaming_client, "stream_json") as mock_stream:
        with patch.object(
            client,
            "_send_api_request",
            new_callable=AsyncMock,
            return_value=response_data,
        ) as mock_request:
            resources = []
            async for resource_batch in client.get_managed_resources(application):
                resources.extend(resource_batch)

            # Should use direct API request, not streaming
            mock_request.assert_called_once_with(
                url=f"{client.api_url}/applications/test-app/managed-resources",
                query_params=None,
            )
            mock_stream.assert_not_called()
            assert len(resources) == 2
            # Verify application is added to each resource
            assert all("__application" in resource for resource in resources)


# Tests for custom HTTP headers
def test_argocd_client_custom_headers() -> None:
    custom_headers: dict[str, str] = {
        "X-Custom-Header": "value",
        "CF-Access-Client-Id": "id",
    }
    client = ArgocdClient(
        token="test_token",
        server_url="https://argocd.example.com",
        ignore_server_error=False,
        allow_insecure=True,
        custom_http_headers=json.dumps(custom_headers),
    )

    # Check if Authorization header is present
    assert client.http_client.headers["Authorization"] == "Bearer test_token"
    # Check if custom headers are present
    assert client.http_client.headers["X-Custom-Header"] == "value"
    assert client.http_client.headers["CF-Access-Client-Id"] == "id"


def test_argocd_client_without_custom_headers() -> None:
    client = ArgocdClient(
        token="test_token",
        server_url="https://argocd.example.com",
        ignore_server_error=False,
        allow_insecure=True,
    )

    assert client.http_client.headers["Authorization"] == "Bearer test_token"
    assert "X-Custom-Header" not in client.http_client.headers


@pytest.mark.asyncio
async def test_get_resources_for_available_clusters_multiple_clusters_yields_all_batches(
    mock_argocd_client: ArgocdClient,
) -> None:
    """Test that all batches from multiple clusters are yielded."""
    cluster_names = [f"cluster-{i}" for i in range(5)]
    mock_clusters = [{"name": name} for name in cluster_names]

    # Each cluster returns 2 batches of items
    cluster_items: dict[str, list[list[dict[str, Any]]]] = {
        name: [
            [{"name": f"{name}-item-{j}"} for j in range(3)],
            [{"name": f"{name}-item-{j}"} for j in range(3, 5)],
        ]
        for name in cluster_names
    }

    async def fake_get_paginated(
        url: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        cluster_name = params["selector"].split("=")[1]  # type: ignore[index]
        for batch in cluster_items[cluster_name]:
            yield batch

    with patch.object(
        mock_argocd_client, "get_available_clusters", new_callable=AsyncMock
    ) as mock_get_clusters:
        mock_get_clusters.return_value = mock_clusters

        with patch.object(
            mock_argocd_client,
            "get_paginated_resources",
            side_effect=fake_get_paginated,
        ):
            all_resources: list[dict[str, Any]] = []
            async for batch in mock_argocd_client.get_resources_for_available_clusters(
                resource_kind=ObjectKind.APPLICATION
            ):
                all_resources.extend(batch)

    # Every item from every cluster must appear
    assert len(all_resources) == 5 * 5  # 5 clusters × 5 items each
    for name in cluster_names:
        for j in range(5):
            assert {"name": f"{name}-item-{j}"} in all_resources


@pytest.mark.asyncio
async def test_get_resources_for_available_clusters_concurrency_is_bounded() -> None:
    """Test that the semaphore limits the number of concurrent get_paginated_resources iterators."""
    concurrency_limit = MAXIMUM_CONCURRENT_CLUSTER_REQUESTS
    # Use more clusters than the concurrency limit to actually test bounding
    num_clusters = concurrency_limit + 10
    cluster_names = [f"cluster-{i}" for i in range(num_clusters)]
    mock_clusters = [{"name": name} for name in cluster_names]

    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=True,
        allow_insecure=True,
        use_streaming=True,
    )

    async def fake_get_paginated(
        url: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        nonlocal in_flight, max_in_flight

        async with lock:
            in_flight += 1
            if in_flight > max_in_flight:
                max_in_flight = in_flight

        # Simulate async I/O so other iterators can be scheduled concurrently
        await asyncio.sleep(0.01)
        yield [{"name": f"{params['selector']}-item"}]  # type: ignore[index]

        async with lock:
            in_flight -= 1

    with patch.object(
        client, "get_available_clusters", new_callable=AsyncMock
    ) as mock_get_clusters:
        mock_get_clusters.return_value = mock_clusters

        with patch.object(
            client,
            "get_paginated_resources",
            side_effect=fake_get_paginated,
        ):
            all_resources: list[dict[str, Any]] = []
            async for batch in client.get_resources_for_available_clusters(
                resource_kind=ObjectKind.APPLICATION
            ):
                all_resources.extend(batch)

    # All clusters produced results
    assert len(all_resources) == num_clusters

    # Concurrency never exceeded the semaphore limit
    assert max_in_flight <= concurrency_limit, (
        f"Max in-flight iterators ({max_in_flight}) exceeded "
        f"semaphore limit ({concurrency_limit})"
    )
    # Concurrency was actually used (not purely sequential)
    assert (
        max_in_flight > 1
    ), f"Expected concurrent execution but max in-flight was {max_in_flight}"
    # All iterators finished
    assert in_flight == 0
