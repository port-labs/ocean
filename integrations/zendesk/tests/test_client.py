"""
Tests for Zendesk client

Testing the ZendeskClient class functionality including:
- Authentication setup
- API request handling
- Pagination
- Rate limiting
- Error handling

Based on Ocean testing patterns and Zendesk API documentation.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from zendesk.client import ZendeskClient


class TestZendeskClient:
    """Test cases for ZendeskClient"""
    
    def test_client_initialization(self):
        """Test that client initializes correctly with proper auth"""
        subdomain = "test-company"
        email = "test@example.com"
        api_token = "test-token-123"
        
        client = ZendeskClient(subdomain, email, api_token)
        
        assert client.subdomain == subdomain
        assert client.email == email
        assert client.api_token == api_token
        assert client.base_url == f"https://{subdomain}.zendesk.com"
        assert "Authorization" in client.headers
        assert "application/json" in client.headers["Content-Type"]
    
    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        """Test successful connection test"""
        client = ZendeskClient("test", "test@example.com", "token")
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"user": {"id": 123, "name": "Test User"}}
            
            result = await client.test_connection()
            
            assert result is True
            mock_request.assert_called_once_with("GET", "users/me")
    
    @pytest.mark.asyncio 
    async def test_test_connection_failure(self):
        """Test failed connection test"""
        client = ZendeskClient("test", "test@example.com", "token")
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=MagicMock())
            
            result = await client.test_connection()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_paginated_tickets(self, sample_ticket_data):
        """Test ticket pagination"""
        client = ZendeskClient("test", "test@example.com", "token")
        
        with patch.object(client, '_paginate', new_callable=AsyncMock) as mock_paginate:
            mock_paginate.__aiter__ = AsyncMock(return_value=iter([[sample_ticket_data]]))
            
            tickets = []
            async for batch in client.get_paginated_tickets():
                tickets.extend(batch)
            
            assert len(tickets) == 1
            assert tickets[0]["id"] == sample_ticket_data["id"]
            mock_paginate.assert_called_once_with("tickets", None, "tickets")
    
    @pytest.mark.asyncio
    async def test_get_paginated_users(self, sample_user_data):
        """Test user pagination"""
        client = ZendeskClient("test", "test@example.com", "token")
        
        with patch.object(client, '_paginate', new_callable=AsyncMock) as mock_paginate:
            mock_paginate.__aiter__ = AsyncMock(return_value=iter([[sample_user_data]]))
            
            users = []
            async for batch in client.get_paginated_users():
                users.extend(batch)
            
            assert len(users) == 1
            assert users[0]["id"] == sample_user_data["id"]
            mock_paginate.assert_called_once_with("users", None, "users")
    
    @pytest.mark.asyncio
    async def test_get_paginated_organizations(self, sample_organization_data):
        """Test organization pagination"""
        client = ZendeskClient("test", "test@example.com", "token")
        
        with patch.object(client, '_paginate', new_callable=AsyncMock) as mock_paginate:
            mock_paginate.__aiter__ = AsyncMock(return_value=iter([[sample_organization_data]]))
            
            organizations = []
            async for batch in client.get_paginated_organizations():
                organizations.extend(batch)
            
            assert len(organizations) == 1
            assert organizations[0]["id"] == sample_organization_data["id"]
            mock_paginate.assert_called_once_with("organizations", None, "organizations")
    
    @pytest.mark.asyncio
    async def test_rate_limiting_retry(self):
        """Test rate limiting retry logic"""
        client = ZendeskClient("test", "test@example.com", "token")
        
        # Mock the first call to return 429, second to succeed
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "1"}
        
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"success": True}
        mock_response_200.raise_for_status.return_value = None
        
        with patch('port_ocean.utils.http_async_client.get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request.side_effect = [
                mock_response_429,
                mock_response_200
            ]
            mock_get_client.return_value.__aenter__.return_value = mock_client
            
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                result = await client._make_request("GET", "test")
                
                assert result == {"success": True}
                mock_sleep.assert_called_once_with(1)  # Retry after 1 second