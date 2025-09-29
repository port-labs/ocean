"""Tests for OktaUserExporter."""

import pytest
from typing import Any, AsyncGenerator, Dict, List, cast
from unittest.mock import AsyncMock, Mock

from okta.core.exporters.user_exporter import OktaUserExporter
from okta.core.options import (
    ListUserOptions,
    GetUserOptions,
)
from okta.clients.http.client import OktaClient


class TestOktaUserExporter:
    """Test cases for OktaUserExporter."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create a mock client."""
        return Mock(spec=OktaClient)

    @pytest.fixture
    def exporter(self, mock_client: Any) -> OktaUserExporter:
        """Create a test exporter."""
        return OktaUserExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_paginated_resources(
        self, exporter: OktaUserExporter, mock_client: Any
    ) -> None:
        """Test getting paginated user resources."""
        mock_users: List[Dict[str, Any]] = [
            {"id": "user1", "profile": {"email": "user1@test.com"}},
            {"id": "user2", "profile": {"email": "user2@test.com"}},
        ]
        mock_groups: List[Dict[str, Any]] = [{"id": "group1", "name": "Group 1"}]

        async def mock_get_users(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield mock_users

        # Assign async generator function to mock attribute
        object.__setattr__(mock_client, "send_paginated_request", mock_get_users)
        mock_client.get_list_resource = AsyncMock(return_value=mock_groups)

        options: ListUserOptions = {"include_groups": True, "fields": "id,profile"}
        users: List[Dict[str, Any]] = []
        async for user_batch in exporter.get_paginated_resources(options):
            users.extend(user_batch)

        assert len(users) == 2
        assert users[0]["id"] == "user1"
        assert users[0]["groups"] == mock_groups

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_error(
        self, exporter: OktaUserExporter, mock_client: Any
    ) -> None:
        """Test handling errors when enriching user data."""
        mock_users: List[Dict[str, Any]] = [
            {"id": "user1", "profile": {"email": "user1@test.com"}}
        ]

        async def mock_get_users(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield mock_users

        object.__setattr__(mock_client, "send_paginated_request", mock_get_users)

        async def raise_error(*args: Any, **kwargs: Any) -> Any:
            raise Exception("API Error")

        mock_client.get_list_resource = AsyncMock(side_effect=raise_error)

        options: ListUserOptions = {"include_groups": True, "fields": "id,profile"}
        users: List[Dict[str, Any]] = []
        async for user_batch in exporter.get_paginated_resources(options):
            users.extend(user_batch)

        # Should still return the user even if enrichment fails (exceptions are swallowed)
        assert len(users) == 1
        assert users[0]["id"] == "user1"
        # User should not have groups since enrichment failed
        assert "groups" not in users[0]

    @pytest.mark.asyncio
    async def test_get_resource(self) -> None:
        """Test getting a single user resource."""
        mock_client: OktaClient = Mock(spec=OktaClient)
        exporter = OktaUserExporter(mock_client)

        mock_user = {"id": "user1", "profile": {"email": "user1@example.com"}}
        mock_groups = [{"id": "group1", "name": "Group 1"}]

        # Mock the client methods
        cast(Any, mock_client).get_single_resource = AsyncMock(return_value=mock_user)
        cast(Any, mock_client).get_list_resource = AsyncMock(return_value=mock_groups)

        options: GetUserOptions = {"user_id": "user1", "include_groups": True}

        user: Dict[str, Any] = await exporter.get_resource(options)

        assert user["id"] == "user1"
        assert user["groups"] == mock_groups
