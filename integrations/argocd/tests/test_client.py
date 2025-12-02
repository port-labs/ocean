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
                    params={"cluster": "test-cluster"},
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
            url=f"{mock_argocd_client.api_url}/clusters", target_items_path="items"
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
                url=f"{mock_argocd_client.api_url}/clusters", target_items_path="items"
            )


# Tests for streaming vs non-streaming functionality
@pytest.mark.asyncio
async def test_fetch_paginated_data_success() -> None:
    """Test _fetch_paginated_data method with successful pagination"""
    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=False,
        allow_insecure=True,
        use_streaming=False,
    )

    # Mock responses for different pages
    # First page: full page (100 items) to trigger continuation
    page1_items = [{"id": i, "name": f"item{i}"} for i in range(100)]
    # Second page: partial page (less than 100 items) to trigger stop
    page2_items = [{"id": 100, "name": "item100"}, {"id": 101, "name": "item101"}]

    page_responses = [
        {"items": page1_items},
        {"items": page2_items},
    ]

    with patch.object(
        client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = page_responses

        all_items = []
        async for items in client._fetch_paginated_data(
            url="https://test.com/api", query_params={"filter": "test"}
        ):
            all_items.extend(items)

        # Should have called 2 times (1 full page, 1 partial page)
        assert mock_request.call_count == 2
        assert len(all_items) == 102
        assert all_items[0]["name"] == "item0"
        assert all_items[99]["name"] == "item99"
        assert all_items[100]["name"] == "item100"
        assert all_items[101]["name"] == "item101"

        # Verify correct pagination parameters
        calls = mock_request.call_args_list
        assert calls[0][1]["query_params"] == {"filter": "test", "page": 0, "size": 100}
        assert calls[1][1]["query_params"] == {"filter": "test", "page": 1, "size": 100}


@pytest.mark.asyncio
async def test_fetch_paginated_data_with_error() -> None:
    """Test _fetch_paginated_data handles errors correctly"""
    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=False,
        allow_insecure=True,
        use_streaming=False,
    )

    with patch.object(
        client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            async for _ in client._fetch_paginated_data(url="https://test.com/api"):
                pass


@pytest.mark.asyncio
async def test_fetch_paginated_data_with_ignored_error() -> None:
    """Test _fetch_paginated_data with ignore_server_error=True"""
    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=True,
        allow_insecure=True,
        use_streaming=False,
    )

    with patch.object(
        client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = Exception("API Error")

        items = []
        async for batch in client._fetch_paginated_data(url="https://test.com/api"):
            items.extend(batch)

        assert len(items) == 0  # Should return empty due to error being ignored


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
        with patch.object(client, "_fetch_paginated_data") as mock_paginated:
            clusters = []
            async for cluster_batch in client.get_clusters():
                clusters.extend(cluster_batch)

            # Should use streaming, not paginated
            mock_stream.assert_called_once()
            mock_paginated.assert_not_called()
            assert len(clusters) == 2


@pytest.mark.asyncio
async def test_get_clusters_with_streaming_disabled() -> None:
    """Test get_clusters uses paginated requests when streaming disabled"""
    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=False,
        allow_insecure=True,
        use_streaming=False,
    )

    response_data = [
        {"name": "cluster-1", "connectionState": {"status": "Successful"}},
        {"name": "cluster-2", "connectionState": {"status": "Failed"}},
    ]

    async def mock_fetch_paginated(*args: Any, **kwargs: Any) -> Any:
        yield response_data

    with patch.object(client.streaming_client, "stream_json") as mock_stream:
        with patch.object(
            client, "_fetch_paginated_data", side_effect=mock_fetch_paginated
        ) as mock_paginated:
            clusters = []
            async for cluster_batch in client.get_clusters():
                clusters.extend(cluster_batch)

            # Should use paginated, not streaming
            mock_paginated.assert_called_once()
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

    response_data = [
        {"name": "cluster-1", "connectionState": {"status": "Successful"}},
        {"name": "cluster-2", "connectionState": {"status": "Failed"}},
        {"name": "cluster-3", "connectionState": {"status": "Successful"}},
    ]

    async def mock_fetch_paginated(*args: Any, **kwargs: Any) -> Any:
        yield response_data

    with patch.object(
        client, "_fetch_paginated_data", side_effect=mock_fetch_paginated
    ):
        clusters = []
        async for cluster_batch in client.get_clusters(skip_unavailable_clusters=True):
            clusters.extend(cluster_batch)

        # Should only have successful clusters
        assert len(clusters) == 2
        assert all(c["connectionState"]["status"] == "Successful" for c in clusters)


@pytest.mark.asyncio
async def test_get_resources_for_available_clusters_with_streaming_disabled() -> None:
    """Test get_resources_for_available_clusters uses paginated requests when streaming disabled"""
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

        response_data = [
            {"name": "app1", "metadata": {"uid": "uid1"}},
            {"name": "app2", "metadata": {"uid": "uid2"}},
        ]

        async def mock_fetch_paginated(*args: Any, **kwargs: Any) -> Any:
            yield response_data

        with patch.object(client.streaming_client, "stream_json") as mock_stream:
            with patch.object(
                client, "_fetch_paginated_data", side_effect=mock_fetch_paginated
            ) as mock_paginated:
                resources = []
                async for resource_batch in client.get_resources_for_available_clusters(
                    ObjectKind.APPLICATION
                ):
                    resources.extend(resource_batch)

                # Should use paginated, not streaming
                mock_paginated.assert_called_once_with(
                    url=f"{client.api_url}/applications",
                    query_params={"cluster": "test-cluster"},
                )
                mock_stream.assert_not_called()
                assert len(resources) == 2


@pytest.mark.asyncio
async def test_get_managed_resources_with_streaming_disabled() -> None:
    """Test get_managed_resources uses paginated requests when streaming disabled"""
    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=False,
        allow_insecure=True,
        use_streaming=False,
    )

    application = {"metadata": {"name": "test-app"}}
    response_data = [
        {"kind": "Service", "name": "svc1"},
        {"kind": "Deployment", "name": "deploy1"},
    ]

    async def mock_fetch_paginated(*args: Any, **kwargs: Any) -> Any:
        yield response_data

    with patch.object(client.streaming_client, "stream_json") as mock_stream:
        with patch.object(
            client, "_fetch_paginated_data", side_effect=mock_fetch_paginated
        ) as mock_paginated:
            resources = []
            async for resource_batch in client.get_managed_resources(application):
                resources.extend(resource_batch)

            # Should use paginated, not streaming
            mock_paginated.assert_called_once_with(
                url=f"{client.api_url}/applications/test-app/managed-resources"
            )
            mock_stream.assert_not_called()
            assert len(resources) == 2
            # Verify application is added to each resource
            assert all("__application" in resource for resource in resources)


@pytest.mark.asyncio
async def test_fetch_paginated_data_infinite_loop_prevention() -> None:
    """Test that _fetch_paginated_data terminates properly when API returns empty items"""
    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=False,
        allow_insecure=True,
        use_streaming=False,
    )

    call_count = 0

    async def mock_api_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1

        # First call returns full page, second call returns empty items
        if call_count == 1:
            return {"items": [{"id": i} for i in range(100)]}  # Full page
        else:
            return {"items": []}  # Empty items - should stop iteration

    with patch.object(
        client, "_send_api_request", side_effect=mock_api_request
    ):
        results = []
        async for batch in client._fetch_paginated_data(url="https://test.com/api"):
            results.extend(batch)

        # Should only make 2 calls and stop
        assert call_count == 2
        assert len(results) == 100  # Only first page


@pytest.mark.asyncio
async def test_fetch_paginated_data_partial_page_termination() -> None:
    """Test that _fetch_paginated_data terminates when getting a partial page"""
    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=False,
        allow_insecure=True,
        use_streaming=False,
    )

    call_count = 0

    async def mock_api_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            return {"items": [{"id": i} for i in range(100)]}  # Full page
        elif call_count == 2:
            return {"items": [{"id": i} for i in range(50)]}  # Partial page - should stop
        else:
            # This should never be called
            return {"items": [{"id": 999}]}

    with patch.object(
        client, "_send_api_request", side_effect=mock_api_request
    ):
        results = []
        async for batch in client._fetch_paginated_data(url="https://test.com/api"):
            results.extend(batch)

        # Should only make 2 calls and stop on partial page
        assert call_count == 2
        assert len(results) == 150  # First page + partial page


@pytest.mark.asyncio
async def test_fetch_paginated_data_with_break_vs_return_behavior() -> None:
    """Test that using return instead of break properly terminates async generator"""
    import asyncio

    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=False,
        allow_insecure=True,
        use_streaming=False,
    )

    call_count = 0

    async def mock_api_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"items": [{"id": i} for i in range(100)]}  # Full page
        else:
            return {"items": []}  # Empty items - should trigger return and stop

    with patch.object(
        client, "_send_api_request", side_effect=mock_api_request
    ):
        # Test that the async generator terminates properly with a timeout
        results = []

        async def collect_with_timeout():
            async for batch in client._fetch_paginated_data(url="https://test.com/api"):
                results.extend(batch)

        # This should complete quickly, not hang indefinitely
        await asyncio.wait_for(collect_with_timeout(), timeout=1.0)

        assert len(results) == 100  # Full page of data
        assert call_count == 2  # First call gets data, second gets empty and terminates


@pytest.mark.asyncio
async def test_fetch_paginated_data_error_handling_terminates_properly() -> None:
    """Test that _fetch_paginated_data terminates properly on errors"""
    client = ArgocdClient(
        token="test_token",
        server_url="https://localhost:8080",
        ignore_server_error=True,  # Ignore errors
        allow_insecure=True,
        use_streaming=False,
    )

    call_count = 0

    async def mock_api_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            return {"items": [{"id": i} for i in range(100)]}  # Full page to trigger next call
        else:
            raise Exception("API Error")  # Should terminate generator

    with patch.object(
        client, "_send_api_request", side_effect=mock_api_request
    ):
        results = []
        async for batch in client._fetch_paginated_data(url="https://test.com/api"):
            results.extend(batch)

        # Should get first page then terminate on error
        assert call_count == 2
        assert len(results) == 100
