from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import Mock

import pytest

from harbor.clients.http.client import HarborClient
from harbor.core.exporters.user_exporter import HarborUserExporter


class TestHarborUserExporter:
    """Test cases for HarborUserExporter."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create a mock Harbor client."""
        return Mock(spec=HarborClient)

    @pytest.fixture
    def exporter(self, mock_client: Any) -> HarborUserExporter:
        """Create a test exporter instance."""
        return HarborUserExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_paginated_resources_yields_user_batches(
        self, exporter: HarborUserExporter, mock_client: Any
    ) -> None:
        """Test get_paginated_resources yields batches of users."""
        mock_users: List[Dict[str, Any]] = [
            {"user_id": 1, "username": "user1"},
            {"user_id": 2, "username": "user2"},
        ]

        async def mock_paginated_request(
            endpoint: str, params: Dict[str, Any]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield mock_users

        object.__setattr__(mock_client, "send_paginated_request", mock_paginated_request)

        users: List[Dict[str, Any]] = []
        async for batch in exporter.get_paginated_resources({}):
            users.extend(batch)

        assert len(users) == 2
        assert users[0]["username"] == "user1"
        assert users[1]["username"] == "user2"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_passes_sort_and_query_parameters(
        self, exporter: HarborUserExporter, mock_client: Any
    ) -> None:
        """Test get_paginated_resources passes sort and query parameters."""
        received_params = None

        async def mock_paginated_request(
            endpoint: str, params: Dict[str, Any]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            nonlocal received_params
            received_params = params
            yield []

        object.__setattr__(mock_client, "send_paginated_request", mock_paginated_request)

        options = {"q": "admin", "sort": "-username"}
        async for _ in exporter.get_paginated_resources(options):
            pass

        assert received_params == {"q": "admin", "sort": "-username"}

    @pytest.mark.asyncio
    async def test_get_paginated_resources_handles_empty_results(
        self, exporter: HarborUserExporter, mock_client: Any
    ) -> None:
        """Test get_paginated_resources handles empty results gracefully."""

        async def mock_paginated_request(
            endpoint: str, params: Dict[str, Any]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            if False:
                yield []

        object.__setattr__(mock_client, "send_paginated_request", mock_paginated_request)

        users: List[Dict[str, Any]] = []
        async for batch in exporter.get_paginated_resources({}):
            users.extend(batch)

        assert len(users) == 0
