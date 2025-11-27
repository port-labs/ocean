"""
Test configuration for Zendesk integration

Following Ocean testing patterns and pytest best practices.

Purpose: Provide common test fixtures and configuration
Expected output: Reusable test fixtures for Zendesk integration testing
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from zendesk.client import ZendeskClient


@pytest.fixture
def mock_zendesk_client():
    """
    Mock Zendesk client for testing
    
    Purpose: Provide a mocked client to avoid real API calls during testing
    Expected output: Mock ZendeskClient instance
    """
    client = MagicMock(spec=ZendeskClient)
    client.test_connection = AsyncMock(return_value=True)
    client.get_paginated_tickets = AsyncMock()
    client.get_paginated_users = AsyncMock()
    client.get_paginated_organizations = AsyncMock()
    client.get_all_side_conversations = AsyncMock()
    return client


@pytest.fixture
def sample_ticket_data():
    """
    Sample ticket data for testing
    
    Based on Zendesk ticket API response structure:
    https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/
    """
    return {
        "id": 12345,
        "subject": "Sample support ticket",
        "status": "open",
        "priority": "normal",
        "requester_id": 67890,
        "assignee_id": 11111,
        "organization_id": 22222,
        "created_at": "2024-01-01T12:00:00Z",
        "updated_at": "2024-01-01T14:30:00Z",
        "tags": ["support", "bug"],
        "custom_fields": []
    }


@pytest.fixture 
def sample_user_data():
    """
    Sample user data for testing
    
    Based on Zendesk user API response structure:
    https://developer.zendesk.com/api-reference/ticketing/users/users/
    """
    return {
        "id": 67890,
        "name": "John Doe",
        "email": "john.doe@example.com",
        "role": "end-user",
        "active": True,
        "suspended": False,
        "organization_id": 22222,
        "created_at": "2023-12-01T10:00:00Z",
        "updated_at": "2024-01-01T10:00:00Z",
        "user_fields": {}
    }


@pytest.fixture
def sample_organization_data():
    """
    Sample organization data for testing
    
    Based on Zendesk organization API response structure:
    https://developer.zendesk.com/api-reference/ticketing/organizations/organizations/
    """
    return {
        "id": 22222,
        "name": "Example Corp",
        "domain_names": ["example.com"],
        "shared_tickets": True,
        "created_at": "2023-11-01T09:00:00Z",
        "updated_at": "2024-01-01T09:00:00Z",
        "organization_fields": {}
    }


@pytest.fixture
def sample_side_conversation_data():
    """
    Sample side conversation data for testing
    
    Based on Zendesk side conversation API response structure:
    https://developer.zendesk.com/api-reference/ticketing/side_conversation/side_conversation/
    """
    return {
        "id": "abc123",
        "ticket_id": 12345,
        "state": "open", 
        "subject": "Side conversation about ticket",
        "created_at": "2024-01-01T13:00:00Z",
        "updated_at": "2024-01-01T13:30:00Z",
        "participants": [
            {
                "user_id": 67890,
                "name": "John Doe",
                "email": "john.doe@example.com"
            }
        ]
    }


@pytest.fixture
def sample_webhook_data():
    """
    Sample webhook data for testing
    
    Based on Zendesk webhook payload structure:
    https://developer.zendesk.com/api-reference/webhooks/event-types/webhook-event-types/
    """
    return {
        "account_id": "test-account-123",
        "event_type": "zen:event-type:ticket.created",
        "detail": {
            "id": 12345,
            "subject": "New support ticket",
            "status": "new",
            "priority": "normal",
            "requester_id": 67890,
            "created_at": "2024-01-01T12:00:00Z"
        },
        "event": {}
    }