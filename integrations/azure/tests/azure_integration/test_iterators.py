"""Tests for Azure resource iterators - the core generic handler logic"""

from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from azure_integration.iterators import (
    resource_base_kind_iterator,
    resource_extention_kind_iterator,
)


class TestResourceBaseKindIterator:
    """Test the core generic iterator that handles all base resource kinds"""

    @pytest.mark.asyncio
    async def test_iterator_fetches_service_bus_namespace(
        self,
        mock_azure_credential: AsyncMock,
        mock_service_bus_namespace: Dict[str, Any],
    ) -> None:
        """Test iterator can fetch ServiceBus namespace"""
        mock_resource = MagicMock()
        mock_resource.as_dict.return_value = mock_service_bus_namespace

        async def mock_list_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[Any, None]:
            yield mock_resource

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "azure_integration.iterators.ResourceManagementClient",
            return_value=mock_client,
        ):
            with patch(
                "azure_integration.iterators.list_resources",
                side_effect=mock_list_resources,
            ):
                results: List[List[Dict[str, Any]]] = []
                async for batch in resource_base_kind_iterator(
                    credential=mock_azure_credential,
                    subscription_id="test-sub-id",
                    resource_kind="Microsoft.ServiceBus/namespaces",
                    api_version="2021-11-01",
                ):
                    results.append(batch)

                # Verify we got results
                assert len(results) > 0
                all_resources = [item for batch in results for item in batch]
                assert len(all_resources) == 1
                assert all_resources[0]["type"] == "Microsoft.ServiceBus/namespaces"
                assert all_resources[0]["properties"]["status"] == "Active"

    @pytest.mark.asyncio
    async def test_iterator_fetches_application_insights(
        self,
        mock_azure_credential: AsyncMock,
        mock_application_insights: Dict[str, Any],
    ) -> None:
        """Test iterator can fetch Application Insights"""
        mock_resource = MagicMock()
        mock_resource.as_dict.return_value = mock_application_insights

        async def mock_list_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[Any, None]:
            yield mock_resource

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "azure_integration.iterators.ResourceManagementClient",
            return_value=mock_client,
        ):
            with patch(
                "azure_integration.iterators.list_resources",
                side_effect=mock_list_resources,
            ):
                results: List[List[Dict[str, Any]]] = []
                async for batch in resource_base_kind_iterator(
                    credential=mock_azure_credential,
                    subscription_id="test-sub-id",
                    resource_kind="Microsoft.Insights/components",
                    api_version="2020-02-02",
                ):
                    results.append(batch)

                assert len(results) > 0
                all_resources = [item for batch in results for item in batch]
                assert len(all_resources) == 1
                assert all_resources[0]["type"] == "Microsoft.Insights/components"
                assert all_resources[0]["properties"]["InstrumentationKey"]

    @pytest.mark.asyncio
    async def test_iterator_fetches_key_vault(
        self,
        mock_azure_credential: AsyncMock,
        mock_key_vault: Dict[str, Any],
    ) -> None:
        """Test iterator can fetch Key Vault"""
        mock_resource = MagicMock()
        mock_resource.as_dict.return_value = mock_key_vault

        async def mock_list_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[Any, None]:
            yield mock_resource

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "azure_integration.iterators.ResourceManagementClient",
            return_value=mock_client,
        ):
            with patch(
                "azure_integration.iterators.list_resources",
                side_effect=mock_list_resources,
            ):
                results: List[List[Dict[str, Any]]] = []
                async for batch in resource_base_kind_iterator(
                    credential=mock_azure_credential,
                    subscription_id="test-sub-id",
                    resource_kind="Microsoft.KeyVault/vaults",
                    api_version="2023-07-01",
                ):
                    results.append(batch)

                assert len(results) > 0
                all_resources = [item for batch in results for item in batch]
                assert len(all_resources) == 1
                assert all_resources[0]["type"] == "Microsoft.KeyVault/vaults"
                assert all_resources[0]["properties"]["vaultUri"]

    @pytest.mark.asyncio
    async def test_iterator_handles_multiple_resources(
        self,
        mock_azure_credential: AsyncMock,
        mock_service_bus_namespace: Dict[str, Any],
        mock_application_insights: Dict[str, Any],
    ) -> None:
        """Test iterator can handle multiple resources in batch"""
        mock_resource1 = MagicMock()
        mock_resource1.as_dict.return_value = mock_service_bus_namespace

        mock_resource2 = MagicMock()
        second_namespace = mock_service_bus_namespace.copy()
        second_namespace["name"] = "test-namespace-2"
        mock_resource2.as_dict.return_value = second_namespace

        async def mock_list_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[Any, None]:
            yield mock_resource1
            yield mock_resource2

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "azure_integration.iterators.ResourceManagementClient",
            return_value=mock_client,
        ):
            with patch(
                "azure_integration.iterators.list_resources",
                side_effect=mock_list_resources,
            ):
                results: List[List[Dict[str, Any]]] = []
                async for batch in resource_base_kind_iterator(
                    credential=mock_azure_credential,
                    subscription_id="test-sub-id",
                    resource_kind="Microsoft.ServiceBus/namespaces",
                    api_version="2021-11-01",
                ):
                    results.append(batch)

                all_resources = [item for batch in results for item in batch]
                assert len(all_resources) == 2
                assert all_resources[0]["name"] == "test-namespace"
                assert all_resources[1]["name"] == "test-namespace-2"

    @pytest.mark.asyncio
    async def test_iterator_handles_empty_results(
        self, mock_azure_credential: AsyncMock
    ) -> None:
        """Test iterator handles empty results gracefully"""

        async def mock_list_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[Any, None]:
            return
            yield

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "azure_integration.iterators.ResourceManagementClient",
            return_value=mock_client,
        ):
            with patch(
                "azure_integration.iterators.list_resources",
                side_effect=mock_list_resources,
            ):
                results: List[List[Dict[str, Any]]] = []
                async for batch in resource_base_kind_iterator(
                    credential=mock_azure_credential,
                    subscription_id="test-sub-id",
                    resource_kind="Microsoft.ServiceBus/namespaces",
                    api_version="2021-11-01",
                ):
                    results.append(batch)

                assert len(results) == 1
                assert len(results[0]) == 0


class TestResourceExtensionKindIterator:
    """Test the extension resource iterator for ServiceBus child resources"""

    @pytest.mark.asyncio
    async def test_iterator_fetches_service_bus_queue(
        self,
        mock_azure_credential: AsyncMock,
        mock_service_bus_namespace: Dict[str, Any],
        mock_service_bus_queue: Dict[str, Any],
    ) -> None:
        """Test iterator can fetch ServiceBus queue (extension resource)"""
        mock_parent = MagicMock()
        mock_parent.as_dict.return_value = mock_service_bus_namespace

        mock_queue = MagicMock()
        mock_queue.as_dict.return_value = mock_service_bus_queue

        call_count = [0]

        async def mock_list_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[Any, None]:
            call_count[0] += 1
            if call_count[0] == 1:
                yield mock_parent
            else:
                yield mock_queue

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "azure_integration.iterators.ResourceManagementClient",
            return_value=mock_client,
        ):
            with patch(
                "azure_integration.iterators.list_resources",
                side_effect=mock_list_resources,
            ):
                results: List[List[Dict[str, Any]]] = []
                async for batch in resource_extention_kind_iterator(
                    credential=mock_azure_credential,
                    subscription_id="test-sub-id",
                    resource_kind="Microsoft.ServiceBus/namespaces/queues",
                    api_version="2021-11-01",
                ):
                    results.append(batch)

                all_resources = [item for batch in results for item in batch]
                assert len(all_resources) > 0
                assert (
                    all_resources[0]["type"] == "Microsoft.ServiceBus/namespaces/queues"
                )

    @pytest.mark.asyncio
    async def test_iterator_fetches_service_bus_topic(
        self,
        mock_azure_credential: AsyncMock,
        mock_service_bus_namespace: Dict[str, Any],
        mock_service_bus_topic: Dict[str, Any],
    ) -> None:
        """Test iterator can fetch ServiceBus topic (extension resource)"""
        mock_parent = MagicMock()
        mock_parent.as_dict.return_value = mock_service_bus_namespace

        mock_topic = MagicMock()
        mock_topic.as_dict.return_value = mock_service_bus_topic

        call_count = [0]

        async def mock_list_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[Any, None]:
            call_count[0] += 1
            if call_count[0] == 1:
                yield mock_parent
            else:
                yield mock_topic

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "azure_integration.iterators.ResourceManagementClient",
            return_value=mock_client,
        ):
            with patch(
                "azure_integration.iterators.list_resources",
                side_effect=mock_list_resources,
            ):
                results: List[List[Dict[str, Any]]] = []
                async for batch in resource_extention_kind_iterator(
                    credential=mock_azure_credential,
                    subscription_id="test-sub-id",
                    resource_kind="Microsoft.ServiceBus/namespaces/topics",
                    api_version="2021-11-01",
                ):
                    results.append(batch)

                all_resources = [item for batch in results for item in batch]
                assert len(all_resources) > 0
                assert (
                    all_resources[0]["type"] == "Microsoft.ServiceBus/namespaces/topics"
                )

    @pytest.mark.asyncio
    async def test_iterator_fetches_service_bus_subscription(
        self,
        mock_azure_credential: AsyncMock,
        mock_service_bus_namespace: Dict[str, Any],
        mock_service_bus_topic: Dict[str, Any],
        mock_service_bus_subscription: Dict[str, Any],
    ) -> None:
        """Test iterator can fetch ServiceBus subscription (nested extension)"""
        mock_namespace = MagicMock()
        mock_namespace.as_dict.return_value = mock_service_bus_namespace

        mock_topic_obj = MagicMock()
        mock_topic_obj.as_dict.return_value = mock_service_bus_topic

        mock_sub = MagicMock()
        mock_sub.as_dict.return_value = mock_service_bus_subscription

        call_count = [0]

        async def mock_list_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[Any, None]:
            call_count[0] += 1
            if call_count[0] == 1:
                yield mock_namespace
            elif call_count[0] == 2:
                yield mock_topic_obj
            else:
                yield mock_sub

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "azure_integration.iterators.ResourceManagementClient",
            return_value=mock_client,
        ):
            with patch(
                "azure_integration.iterators.list_resources",
                side_effect=mock_list_resources,
            ):
                results: List[List[Dict[str, Any]]] = []
                async for batch in resource_extention_kind_iterator(
                    credential=mock_azure_credential,
                    subscription_id="test-sub-id",
                    resource_kind="Microsoft.ServiceBus/namespaces/topics/subscriptions",
                    api_version="2021-11-01",
                ):
                    results.append(batch)

                all_resources = [item for batch in results for item in batch]
                assert len(all_resources) > 0
                assert (
                    all_resources[0]["type"]
                    == "Microsoft.ServiceBus/namespaces/topics/subscriptions"
                )
