from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager
import pytest

from aws.core.client.paginator import AsyncPaginator


@pytest.mark.asyncio
class TestAsyncPaginator:
    @asynccontextmanager
    async def _mock_cloudcontrol_client(
        self, mock_aiosession: AsyncMock, paginator_mock: Any
    ) -> AsyncGenerator[AsyncMock, None]:
        """Helper to create a mocked cloudcontrol client with custom paginator."""
        mock_cloudcontrol_client = AsyncMock()
        mock_cloudcontrol_client.get_paginator = MagicMock(return_value=paginator_mock)

        # Override the mock_client to handle cloudcontrol service
        original_create_client = mock_aiosession.create_client

        @asynccontextmanager
        async def mock_create_client_with_cloudcontrol(
            service_name: str, **kwargs: Any
        ) -> AsyncGenerator[AsyncMock, None]:
            if service_name == "cloudcontrol":
                yield mock_cloudcontrol_client
            else:
                async with original_create_client(service_name, **kwargs) as client:
                    yield client

        mock_aiosession.create_client = mock_create_client_with_cloudcontrol

        async with mock_aiosession.create_client("cloudcontrol") as client:
            yield client

    async def test_async_paginator(self, mock_aiosession: AsyncMock) -> None:
        # Mock paginator that returns test data
        class MockPaginator:
            async def paginate(
                self, **kwargs: Any
            ) -> AsyncGenerator[Dict[str, Any], None]:
                yield {"ResourceDescriptions": [{"Identifier": "test-id"}]}

        async with self._mock_cloudcontrol_client(
            mock_aiosession, MockPaginator()
        ) as client:
            paginator = AsyncPaginator(client, "list_resources", "ResourceDescriptions")
            results = []

            async for items in paginator.paginate(TypeName="AWS::S3::Bucket"):
                results.extend(items)

            assert len(results) == 1
            assert results[0]["Identifier"] == "test-id"

    async def test_async_paginator_with_batch_size(
        self, mock_aiosession: AsyncMock
    ) -> None:
        # Mock paginator that returns test data
        class MockPaginator:
            async def paginate(
                self, **kwargs: Any
            ) -> AsyncGenerator[Dict[str, Any], None]:
                yield {"ResourceDescriptions": [{"Identifier": "test-id"}]}

        async with self._mock_cloudcontrol_client(
            mock_aiosession, MockPaginator()
        ) as client:
            paginator = AsyncPaginator(client, "list_resources", "ResourceDescriptions")
            batches = []

            async for batch in paginator.paginate(
                batch_size=1, TypeName="AWS::S3::Bucket"
            ):
                batches.append(batch)

            assert len(batches) == 1
            assert len(batches[0]) == 1
            assert batches[0][0]["Identifier"] == "test-id"

    async def test_async_paginator_empty_response(
        self, mock_aiosession: AsyncMock
    ) -> None:
        # Mock paginator that returns empty data
        class EmptyPaginatorMock:
            async def paginate(
                self, **kwargs: Any
            ) -> AsyncGenerator[Dict[str, Any], None]:
                yield {"ResourceDescriptions": []}

        async with self._mock_cloudcontrol_client(
            mock_aiosession, EmptyPaginatorMock()
        ) as client:
            paginator = AsyncPaginator(client, "list_resources", "ResourceDescriptions")
            results = []

            async for items in paginator.paginate(TypeName="AWS::S3::Bucket"):
                results.extend(items)

            assert len(results) == 0
