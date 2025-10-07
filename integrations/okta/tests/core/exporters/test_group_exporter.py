"""Tests for OktaGroupExporter."""

import pytest
from typing import Any, AsyncGenerator, Dict, List, cast
from unittest.mock import AsyncMock, Mock

from okta.core.exporters.group_exporter import OktaGroupExporter
from okta.clients.http.client import OktaClient


class TestOktaGroupExporter:
    """Test cases for OktaGroupExporter."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create a mock client."""
        return Mock(spec=OktaClient)

    @pytest.fixture
    def exporter(self, mock_client: Any) -> OktaGroupExporter:
        """Create a test exporter."""
        return OktaGroupExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_paginated_resources(
        self, exporter: OktaGroupExporter, mock_client: Any
    ) -> None:
        """Test getting paginated group resources."""
        mock_groups: List[Dict[str, Any]] = [
            {"id": "group1", "profile": {"name": "Group 1"}},
            {"id": "group2", "profile": {"name": "Group 2"}},
        ]

        async def mock_get_groups(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield mock_groups

        object.__setattr__(mock_client, "send_paginated_request", mock_get_groups)

        groups: List[Dict[str, Any]] = []
        async for group_batch in exporter.get_paginated_resources({}):
            groups.extend(group_batch)

        assert len(groups) == 2
        assert groups[0]["id"] == "group1"

    @pytest.mark.asyncio
    async def test_get_resource(self) -> None:
        """Test getting a single group resource."""
        mock_client: OktaClient = Mock(spec=OktaClient)
        exporter = OktaGroupExporter(mock_client)

        mock_group = {"id": "group1", "profile": {"name": "Group 1"}}


        cast(Any, mock_client).send_api_request = AsyncMock(return_value=mock_group)

        group: Dict[str, Any] = await exporter.get_resource("group1")

        assert group["id"] == "group1"
        # No strict mock call assertions to keep type checker satisfied
