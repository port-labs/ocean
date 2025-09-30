"""Tests for OktaUserAppsExporter."""

import pytest
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock

from okta.core.exporters.user_apps_exporter import OktaUserAppsExporter
from okta.clients.http.client import OktaClient


class TestOktaUserAppsExporter:
    """Test cases for OktaUserAppsExporter."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create a mock client."""
        return Mock(spec=OktaClient)

    @pytest.fixture
    def exporter(self, mock_client: Any) -> OktaUserAppsExporter:
        """Create a test exporter."""
        return OktaUserAppsExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_resource(
        self, exporter: OktaUserAppsExporter, mock_client: Any
    ) -> None:
        """Test getting user applications."""
        mock_apps: List[Dict[str, Any]] = [
            {"id": "app1", "name": "App 1"},
            {"id": "app2", "name": "App 2"},
        ]

        mock_client.get_list_resource = AsyncMock(return_value=mock_apps)

        result: Dict[str, Any] = await exporter.get_resource("user1")

        assert result == {"applications": mock_apps}

    def test_get_paginated_resources_not_implemented(
        self, exporter: OktaUserAppsExporter
    ) -> None:
        """Test that paginated resources raises NotImplementedError."""
        with pytest.raises(
            NotImplementedError,
            match="Pagination is not supported for user applications endpoint",
        ):
            exporter.get_paginated_resources("user1")
