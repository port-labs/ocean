"""Tests for Azure patch functionality"""

from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from azure_integration.azure_patch import (
    build_full_resources_list_request_patch,
    list_resources,
)


class TestBuildFullResourcesListRequestPatch:
    """Test build_full_resources_list_request_patch function"""

    def test_builds_request_with_resource_type(self) -> None:
        """Test building request with resource type"""
        with patch(
            "azure_integration.azure_patch.old_build_resources_list_request"
        ) as mock_old_build:
            mock_request = MagicMock()
            mock_request.headers = {
                "resource-type": "Microsoft.Storage/storageAccounts",
                "api-version": "2023-01-01",
            }
            mock_old_build.return_value = mock_request

            result = build_full_resources_list_request_patch(
                subscription_id="test-sub-id"
            )

            assert result is not None
            # Verify URL was updated to use resource provider endpoint
            assert "/providers/" in result.url

    def test_builds_request_with_resource_url(self) -> None:
        """Test building request with resource URL"""
        with patch(
            "azure_integration.azure_patch.old_build_resources_list_request"
        ) as mock_old_build:
            mock_request = MagicMock()
            mock_request.headers = {
                "resource-url": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/test-account/blobServices/default/containers",
                "api-version": "2023-01-01",
            }
            mock_old_build.return_value = mock_request

            result = build_full_resources_list_request_patch(
                subscription_id="test-sub-id"
            )

            assert result is not None
            assert result.url is not None


class TestListResources:
    """Test list_resources function"""

    @pytest.mark.asyncio
    async def test_list_resources_with_resource_type(self) -> None:
        """Test listing resources by resource type"""
        mock_client = AsyncMock()

        # Mock resource response
        mock_resource = MagicMock()
        mock_resource.as_dict.return_value = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/test-storage",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "test-storage",
        }

        async def mock_list(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
            yield mock_resource

        mock_client.resources.list = mock_list
        mock_client.resources._config = MagicMock()
        mock_client.resources._api_version = "2023-01-01"

        results = []
        async for resource in list_resources(
            resources_client=mock_client,
            api_version="2023-01-01",
            resource_type="Microsoft.Storage/storageAccounts",
        ):
            results.append(resource)

        assert len(results) == 1
        assert results[0].as_dict()["type"] == "Microsoft.Storage/storageAccounts"

    @pytest.mark.asyncio
    async def test_list_resources_with_resource_url(self) -> None:
        """Test listing resources by resource URL"""
        mock_client = AsyncMock()

        mock_resource = MagicMock()
        mock_resource.as_dict.return_value = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ServiceBus/namespaces/test-ns/queues/test-queue",
            "type": "Microsoft.ServiceBus/namespaces/queues",
            "name": "test-queue",
        }

        async def mock_list(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
            yield mock_resource

        mock_client.resources.list = mock_list
        mock_client.resources._config = MagicMock()
        mock_client.resources._api_version = "2021-11-01"

        results = []
        async for resource in list_resources(
            resources_client=mock_client,
            api_version="2021-11-01",
            resource_url="/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ServiceBus/namespaces/test-ns/queues",
        ):
            results.append(resource)

        assert len(results) == 1
        assert results[0].as_dict()["type"] == "Microsoft.ServiceBus/namespaces/queues"

    @pytest.mark.asyncio
    async def test_list_resources_raises_error_with_both_params(self) -> None:
        """Test that providing both resource_type and resource_url raises error"""
        mock_client = AsyncMock()

        with pytest.raises(
            ValueError,
            match="Only one of resource_type and resource_url can be passed",
        ):
            async for _ in list_resources(
                resources_client=mock_client,
                api_version="2023-01-01",
                resource_type="Microsoft.Storage/storageAccounts",
                resource_url="/some/url",
            ):
                pass

    @pytest.mark.asyncio
    async def test_list_resources_sets_api_version(self) -> None:
        """Test that list_resources sets the correct API version on client"""
        mock_client = AsyncMock()

        async def mock_list(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
            return
            yield

        mock_client.resources.list = mock_list
        mock_client.resources._config = MagicMock()
        mock_client.resources._api_version = "old-version"

        async for _ in list_resources(
            resources_client=mock_client,
            api_version="2023-01-01",
            resource_type="Microsoft.Storage/storageAccounts",
        ):
            pass

        # Verify API version was set
        assert mock_client.resources._config.api_version == "2023-01-01"
        assert mock_client.resources._api_version == "2023-01-01"
