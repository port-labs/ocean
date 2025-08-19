import pytest
from unittest.mock import Mock, AsyncMock

from webhook_processors.ticket_webhook_processor import TicketWebhookProcessor
from webhook_processors.user_webhook_processor import UserWebhookProcessor
from webhook_processors.organization_webhook_processor import OrganizationWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from zendesk.overrides import ZendeskTicketResourceConfig, ZendeskUserResourceConfig, ZendeskOrganizationResourceConfig


class TestTicketWebhookProcessor:
    """Test TicketWebhookProcessor."""

    @pytest.fixture
    def processor(self):
        return TicketWebhookProcessor()

    @pytest.fixture
    def ticket_config(self):
        return Mock(spec=ZendeskTicketResourceConfig)

    @pytest.mark.asyncio
    async def test_should_process_event_ticket_created(self, processor):
        """Test processing ticket.created events."""
        event = WebhookEvent(
            payload={"type": "ticket.created"},
            headers={}
        )
        
        result = await processor.should_process_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_ticket_updated(self, processor):
        """Test processing ticket.updated events."""
        event = WebhookEvent(
            payload={"type": "ticket.updated"},
            headers={}
        )
        
        result = await processor.should_process_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_ticket_deleted(self, processor):
        """Test processing ticket.deleted events."""
        event = WebhookEvent(
            payload={"type": "ticket.deleted"},
            headers={}
        )
        
        result = await processor.should_process_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_not_process_other_events(self, processor):
        """Test not processing non-ticket events."""
        event = WebhookEvent(
            payload={"type": "user.created"},
            headers={}
        )
        
        result = await processor.should_process_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_matching_kinds(self, processor):
        """Test getting matching kinds."""
        event = WebhookEvent(
            payload={"type": "ticket.created"},
            headers={}
        )
        
        result = await processor.get_matching_kinds(event)
        assert result == ["ticket"]

    @pytest.mark.asyncio
    async def test_handle_ticket_deleted_event(self, processor, ticket_config, sample_ticket):
        """Test handling ticket deleted event."""
        payload = {
            "type": "ticket.deleted",
            "ticket": sample_ticket
        }
        
        result = await processor.handle_event(payload, ticket_config)
        
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == [sample_ticket]

    def test_validate_payload_valid(self, processor):
        """Test payload validation with valid payload."""
        payload = {
            "type": "ticket.created",
            "ticket": {"id": 123}
        }
        
        result = processor.validate_payload(payload)
        assert result is True

    def test_validate_payload_invalid(self, processor):
        """Test payload validation with invalid payload."""
        payload = {
            "type": "ticket.created"
            # Missing "ticket" field
        }
        
        result = processor.validate_payload(payload)
        assert result is False


class TestUserWebhookProcessor:
    """Test UserWebhookProcessor."""

    @pytest.fixture
    def processor(self):
        return UserWebhookProcessor()

    @pytest.mark.asyncio
    async def test_should_process_event_user_created(self, processor):
        """Test processing user.created events."""
        event = WebhookEvent(
            payload={"type": "user.created"},
            headers={}
        )
        
        result = await processor.should_process_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_get_matching_kinds(self, processor):
        """Test getting matching kinds."""
        event = WebhookEvent(
            payload={"type": "user.created"},
            headers={}
        )
        
        result = await processor.get_matching_kinds(event)
        assert result == ["user"]

    def test_validate_payload_valid(self, processor):
        """Test payload validation with valid payload."""
        payload = {
            "type": "user.created",
            "user": {"id": 123}
        }
        
        result = processor.validate_payload(payload)
        assert result is True


class TestOrganizationWebhookProcessor:
    """Test OrganizationWebhookProcessor."""

    @pytest.fixture
    def processor(self):
        return OrganizationWebhookProcessor()

    @pytest.mark.asyncio
    async def test_should_process_event_organization_created(self, processor):
        """Test processing organization.created events."""
        event = WebhookEvent(
            payload={"type": "organization.created"},
            headers={}
        )
        
        result = await processor.should_process_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_get_matching_kinds(self, processor):
        """Test getting matching kinds."""
        event = WebhookEvent(
            payload={"type": "organization.created"},
            headers={}
        )
        
        result = await processor.get_matching_kinds(event)
        assert result == ["organization"]

    def test_validate_payload_valid(self, processor):
        """Test payload validation with valid payload."""
        payload = {
            "type": "organization.created",
            "organization": {"id": 123}
        }
        
        result = processor.validate_payload(payload)
        assert result is True