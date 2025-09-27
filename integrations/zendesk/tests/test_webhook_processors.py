"""
Tests for Zendesk webhook processors

Testing webhook processor functionality including:
- Event type validation
- Payload processing
- Event filtering
- Data transformation

Based on Ocean testing patterns and Zendesk webhook documentation.
"""

import pytest
from unittest.mock import MagicMock

from webhook_processors.ticket_webhook_processor import TicketWebhookProcessor
from webhook_processors.user_webhook_processor import UserWebhookProcessor
from webhook_processors.organization_webhook_processor import OrganizationWebhookProcessor


class TestTicketWebhookProcessor:
    """Test cases for TicketWebhookProcessor"""
    
    def test_get_supported_events(self):
        """Test that processor returns correct supported events"""
        processor = TicketWebhookProcessor()
        events = processor.get_supported_events()
        
        assert "zen:event-type:ticket.created" in events
        assert "zen:event-type:ticket.updated" in events
        assert "zen:event-type:ticket.status_changed" in events
        assert "zen:event-type:ticket.deleted" in events
        assert len(events) > 10  # Should have many ticket events
    
    def test_is_supported_event(self):
        """Test event type validation"""
        processor = TicketWebhookProcessor()
        
        assert processor.is_supported_event("zen:event-type:ticket.created") is True
        assert processor.is_supported_event("zen:event-type:user.created") is False
        assert processor.is_supported_event("invalid-event-type") is False
    
    @pytest.mark.asyncio
    async def test_should_process_webhook_valid(self, sample_webhook_data):
        """Test should process valid ticket webhook"""
        processor = TicketWebhookProcessor()
        
        result = await processor.should_process_webhook(sample_webhook_data)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_should_process_webhook_invalid_structure(self):
        """Test should not process webhook with invalid structure"""
        processor = TicketWebhookProcessor()
        invalid_data = {"invalid": "structure"}
        
        result = await processor.should_process_webhook(invalid_data)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_should_process_webhook_unsupported_event(self, sample_webhook_data):
        """Test should not process unsupported event type"""
        processor = TicketWebhookProcessor()
        sample_webhook_data["event_type"] = "zen:event-type:user.created"
        
        result = await processor.should_process_webhook(sample_webhook_data)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_process_webhook_success(self, sample_webhook_data):
        """Test successful webhook processing"""
        processor = TicketWebhookProcessor()
        
        result = await processor.process_webhook(sample_webhook_data, sample_webhook_data)
        
        assert result is not None
        assert len(result) == 1
        assert result[0]["id"] == sample_webhook_data["detail"]["id"]
        assert result[0]["webhook_event_type"] == "zen:event-type:ticket.created"
    
    @pytest.mark.asyncio 
    async def test_process_webhook_no_detail(self, sample_webhook_data):
        """Test webhook processing with missing detail"""
        processor = TicketWebhookProcessor()
        sample_webhook_data.pop("detail")
        
        result = await processor.process_webhook(sample_webhook_data, sample_webhook_data)
        
        assert result is None


class TestUserWebhookProcessor:
    """Test cases for UserWebhookProcessor"""
    
    def test_get_supported_events(self):
        """Test that processor returns correct supported events"""
        processor = UserWebhookProcessor()
        events = processor.get_supported_events()
        
        assert "zen:event-type:user.created" in events
        assert "zen:event-type:user.updated" in events
        assert "zen:event-type:user.deleted" in events
        assert "zen:event-type:user.role_changed" in events
        assert len(events) >= 5  # Should have several user events
    
    @pytest.mark.asyncio
    async def test_process_webhook_role_change(self, sample_webhook_data):
        """Test processing role change event"""
        processor = UserWebhookProcessor()
        sample_webhook_data["event_type"] = "zen:event-type:user.role_changed"
        sample_webhook_data["event"] = {
            "previous": "end-user",
            "current": "agent"
        }
        
        result = await processor.process_webhook(sample_webhook_data, sample_webhook_data)
        
        assert result is not None
        assert len(result) == 1
        assert result[0]["webhook_event_type"] == "zen:event-type:user.role_changed"
        assert result[0]["webhook_event_data"]["previous"] == "end-user"


class TestOrganizationWebhookProcessor:
    """Test cases for OrganizationWebhookProcessor"""
    
    def test_get_supported_events(self):
        """Test that processor returns correct supported events"""
        processor = OrganizationWebhookProcessor()
        events = processor.get_supported_events()
        
        assert "zen:event-type:organization.created" in events
        assert "zen:event-type:organization.updated" in events
        assert "zen:event-type:organization.deleted" in events
        assert "zen:event-type:organization.domain_name_added" in events
        assert len(events) >= 4  # Should have several organization events
    
    @pytest.mark.asyncio
    async def test_process_webhook_domain_change(self, sample_webhook_data):
        """Test processing domain change event"""
        processor = OrganizationWebhookProcessor()
        sample_webhook_data["event_type"] = "zen:event-type:organization.domain_name_added"
        sample_webhook_data["event"] = {
            "domain_name": "newdomain.com"
        }
        
        result = await processor.process_webhook(sample_webhook_data, sample_webhook_data)
        
        assert result is not None
        assert len(result) == 1
        assert result[0]["webhook_event_type"] == "zen:event-type:organization.domain_name_added"
        assert result[0]["webhook_event_data"]["domain_name"] == "newdomain.com"