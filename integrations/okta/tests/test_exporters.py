"""Tests for Okta exporters."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from okta.core.exporters.user_exporter import OktaUserExporter
from okta.core.exporters.group_exporter import OktaGroupExporter
from okta.core.options import ListUserOptions, ListGroupOptions, GetUserOptions, GetGroupOptions
from okta.clients.http.client import OktaClient


class TestOktaUserExporter:
    """Test cases for OktaUserExporter."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        return Mock(spec=OktaRestClient)

    @pytest.fixture
    def exporter(self, mock_client):
        """Create a test exporter."""
        return OktaUserExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_paginated_resources(self, exporter, mock_client):
        """Test getting paginated user resources."""
        mock_users = [
            {"id": "user1", "profile": {"email": "user1@test.com"}},
            {"id": "user2", "profile": {"email": "user2@test.com"}},
        ]
        mock_groups = [{"id": "group1", "name": "Group 1"}]
        mock_apps = [{"id": "app1", "name": "App 1"}]

        async def mock_get_users(*args, **kwargs):
            yield mock_users

        mock_client.get_users = AsyncMock(side_effect=mock_get_users)
        mock_client.get_user_groups = AsyncMock(return_value=mock_groups)
        mock_client.get_user_apps = AsyncMock(return_value=mock_apps)

        options = ListUserOptions(include_groups=True, include_applications=True)
        users = []
        async for user_batch in exporter.get_paginated_resources(options):
            users.extend(user_batch)

        assert len(users) == 2
        assert users[0]["id"] == "user1"
        assert users[0]["groups"] == mock_groups
        assert users[0]["applications"] == mock_apps

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_error(self, exporter, mock_client):
        """Test handling errors when enriching user data."""
        mock_users = [{"id": "user1", "profile": {"email": "user1@test.com"}}]

        async def mock_get_users(*args, **kwargs):
            yield mock_users

        mock_client.get_users = AsyncMock(side_effect=mock_get_users)
        mock_client.get_user_groups = AsyncMock(side_effect=Exception("API Error"))
        mock_client.get_user_apps = AsyncMock(return_value=[])

        options = ListUserOptions(include_groups=True, include_applications=True)
        users = []
        async for user_batch in exporter.get_paginated_resources(options):
            users.extend(user_batch)

        # Should still return the user even if enrichment fails
        assert len(users) == 1
        assert users[0]["id"] == "user1"

    @pytest.mark.asyncio
    async def test_get_resource(self):
        """Test getting a single user resource."""
        mock_client = Mock(spec=OktaClient)
        exporter = OktaUserExporter(mock_client)

        mock_user = {"id": "user1", "profile": {"email": "user1@example.com"}}
        mock_groups = [{"id": "group1", "name": "Group 1"}]
        mock_apps = [{"id": "app1", "name": "App 1"}]

        mock_client.get_user = AsyncMock(return_value=mock_user)
        mock_client.get_user_groups = AsyncMock(return_value=mock_groups)
        mock_client.get_user_apps = AsyncMock(return_value=mock_apps)

        options = GetUserOptions(
            user_id="user1",
            include_groups=True,
            include_applications=True,
        )

        user = await exporter.get_resource(options)

        assert user["id"] == "user1"
        assert user["groups"] == mock_groups
        assert user["applications"] == mock_apps
        mock_client.get_user.assert_called_once_with("user1")
        mock_client.get_user_groups.assert_called_once_with("user1")
        mock_client.get_user_apps.assert_called_once_with("user1")


class TestOktaGroupExporter:
    """Test cases for OktaGroupExporter."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        return Mock(spec=OktaRestClient)

    @pytest.fixture
    def exporter(self, mock_client):
        """Create a test exporter."""
        return OktaGroupExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_paginated_resources(self, exporter, mock_client):
        """Test getting paginated group resources."""
        mock_groups = [
            {"id": "group1", "profile": {"name": "Group 1"}},
            {"id": "group2", "profile": {"name": "Group 2"}},
        ]
        mock_members = [{"id": "user1", "name": "User 1"}]

        async def mock_get_groups(*args, **kwargs):
            yield mock_groups

        mock_client.get_groups = AsyncMock(side_effect=mock_get_groups)
        mock_client.get_group_members = AsyncMock(return_value=mock_members)

        options = ListGroupOptions(include_members=True)
        groups = []
        async for group_batch in exporter.get_paginated_resources(options):
            groups.extend(group_batch)

        assert len(groups) == 2
        assert groups[0]["id"] == "group1"
        assert groups[0]["members"] == mock_members

    @pytest.mark.asyncio
    async def test_get_resource(self):
        """Test getting a single group resource."""
        mock_client = Mock(spec=OktaClient)
        exporter = OktaGroupExporter(mock_client)

        mock_group = {"id": "group1", "profile": {"name": "Group 1"}}
        mock_members = [{"id": "user1", "name": "User 1"}]

        mock_client.get_group = AsyncMock(return_value=mock_group)
        mock_client.get_group_members = AsyncMock(return_value=mock_members)

        options = GetGroupOptions(
            group_id="group1",
            include_members=True,
        )

        group = await exporter.get_resource(options)

        assert group["id"] == "group1"
        assert group["members"] == mock_members
        mock_client.get_group.assert_called_once_with("group1")
        mock_client.get_group_members.assert_called_once_with("group1")


 
