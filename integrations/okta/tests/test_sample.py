"""Sample tests for Okta integration"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from okta.client import OktaClient


class TestOktaClient:
    """Test cases for Okta client"""

    @pytest.fixture
    def mock_okta_client(self):
        """Mock Okta client fixture"""
        return OktaClient(
            domain="dev-123456.okta.com",
            api_token="test_token"
        )

    def test_client_initialization(self, mock_okta_client):
        """Test client initialization"""
        assert mock_okta_client.domain == "https://dev-123456.okta.com"
        assert mock_okta_client.api_token == "test_token"
        assert mock_okta_client.base_url == "https://dev-123456.okta.com/api/v1"
        assert "SSWS test_token" in mock_okta_client.headers["Authorization"]

    def test_client_initialization_with_https(self):
        """Test client initialization with https domain"""
        client = OktaClient(
            domain="https://dev-123456.okta.com",
            api_token="test_token"
        )
        assert client.domain == "https://dev-123456.okta.com"

    def test_client_initialization_strips_trailing_slash(self):
        """Test client initialization strips trailing slash"""
        client = OktaClient(
            domain="dev-123456.okta.com/",
            api_token="test_token"
        )
        assert client.domain == "https://dev-123456.okta.com"

    @pytest.mark.asyncio
    async def test_get_user_roles_error_handling(self, mock_okta_client):
        """Test error handling in get_user_roles"""
        with pytest.patch.object(mock_okta_client, '_make_request') as mock_request:
            mock_request.side_effect = Exception("API Error")
            
            result = await mock_okta_client.get_user_roles("test_user_id")
            assert result == []

    @pytest.mark.asyncio
    async def test_get_user_groups_error_handling(self, mock_okta_client):
        """Test error handling in get_user_groups"""
        with pytest.patch.object(mock_okta_client, '_make_request') as mock_request:
            mock_request.side_effect = Exception("API Error")
            
            result = await mock_okta_client.get_user_groups("test_user_id")
            assert result == []

    @pytest.mark.asyncio
    async def test_get_group_users_error_handling(self, mock_okta_client):
        """Test error handling in get_group_users"""
        with pytest.patch.object(mock_okta_client, '_make_request') as mock_request:
            mock_request.side_effect = Exception("API Error")
            
            result = await mock_okta_client.get_group_users("test_group_id")
            assert result == []

    @pytest.mark.asyncio
    async def test_enrich_groups_with_members(self, mock_okta_client):
        """Test enriching groups with members"""
        groups = [
            {"id": "group1", "profile": {"name": "Engineering"}},
            {"id": "group2", "profile": {"name": "Marketing"}}
        ]
        
        with pytest.patch.object(mock_okta_client, 'get_group_users') as mock_get_users:
            mock_get_users.return_value = [{"id": "user1", "profile": {"displayName": "John Doe"}}]
            
            result = await mock_okta_client.enrich_groups_with_members(groups)
            
            assert len(result) == 2
            assert all("members" in group for group in result)
            assert result[0]["members"] == [{"id": "user1", "profile": {"displayName": "John Doe"}}]