import pytest
from unittest.mock import Mock, AsyncMock
from zendesk.client import ZendeskClient


@pytest.fixture
def mock_zendesk_client():
    """Mock ZendeskClient for testing."""
    client = Mock(spec=ZendeskClient)
    client.test_connection = AsyncMock(return_value=True)
    client.get_tickets = AsyncMock(return_value=iter([]))
    client.get_users = AsyncMock(return_value=iter([]))
    client.get_organizations = AsyncMock(return_value=iter([]))
    client.get_groups = AsyncMock(return_value=iter([]))
    client.get_brands = AsyncMock(return_value=iter([]))
    client.get_single_ticket = AsyncMock(return_value={})
    client.get_single_user = AsyncMock(return_value={})
    client.get_single_organization = AsyncMock(return_value={})
    client.get_single_group = AsyncMock(return_value={})
    return client


@pytest.fixture
def sample_ticket():
    """Sample Zendesk ticket data."""
    return {
        "id": 12345,
        "subject": "Test ticket subject",
        "status": "open",
        "priority": "normal",
        "assignee_id": 67890,
        "organization_id": 11111,
        "requester_id": 22222,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "description": "Test ticket description",
        "tags": ["test", "example"],
        "type": "incident"
    }


@pytest.fixture
def sample_user():
    """Sample Zendesk user data."""
    return {
        "id": 67890,
        "name": "John Doe",
        "email": "john.doe@example.com",
        "role": "agent",
        "organization_id": 11111,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "active": True,
        "verified": True,
        "time_zone": "UTC"
    }


@pytest.fixture
def sample_organization():
    """Sample Zendesk organization data."""
    return {
        "id": 11111,
        "name": "Example Organization",
        "external_id": "org-123",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "domain_names": ["example.com"],
        "details": "Example organization details"
    }


@pytest.fixture
def sample_group():
    """Sample Zendesk group data."""
    return {
        "id": 33333,
        "name": "Support Team",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "deleted": False
    }


@pytest.fixture
def sample_brand():
    """Sample Zendesk brand data."""
    return {
        "id": 44444,
        "name": "Example Brand",
        "brand_url": "https://example.zendesk.com",
        "has_help_center": True,
        "active": True,
        "default": True
    }