import pytest
from unittest.mock import AsyncMock, patch

from webhook_processors.scan_webhook_processor import ScanWebhookProcessor


class TestScanWebhookProcessor:
    """Tests for ScanWebhookProcessor."""

    @pytest.fixture
    def processor(self):
        """Scan webhook processor fixture."""
        return ScanWebhookProcessor()

    def test_supported_events(self, processor):
        """Test that processor supports expected events."""
        expected_events = [
            "SCAN_STARTED",
            "SCAN_COMPLETED",
            "SCAN_FAILED", 
            "SCAN_CANCELED"
        ]
        assert processor.SUPPORTED_EVENTS == expected_events

    def test_map_event_to_status(self, processor):
        """Test event type to status mapping."""
        test_cases = [
            ("SCAN_STARTED", "Running"),
            ("SCAN_COMPLETED", "Completed"),
            ("SCAN_FAILED", "Failed"),
            ("SCAN_CANCELED", "Canceled"),
            ("UNKNOWN_EVENT", "Unknown")
        ]
        
        for event_type, expected_status in test_cases:
            result = processor._map_event_to_status(event_type)
            assert result == expected_status

    def test_validate_webhook_payload_valid(self, processor):
        """Test validation of valid webhook payload."""
        payload = {
            "eventType": "SCAN_COMPLETED",
            "timestamp": "2024-01-23T10:30:00.000Z",
            "scanData": {
                "id": "scan-123",
                "projectId": "project-456"
            }
        }
        
        assert processor._validate_webhook_payload(payload) is True

    def test_validate_webhook_payload_missing_required_fields(self, processor):
        """Test validation fails for missing required fields."""
        # Missing eventType
        payload1 = {
            "timestamp": "2024-01-23T10:30:00.000Z",
            "scanData": {"id": "scan-123"}
        }
        assert processor._validate_webhook_payload(payload1) is False
        
        # Missing timestamp  
        payload2 = {
            "eventType": "SCAN_COMPLETED",
            "scanData": {"id": "scan-123"}
        }
        assert processor._validate_webhook_payload(payload2) is False
        
        # Missing scanData
        payload3 = {
            "eventType": "SCAN_COMPLETED",
            "timestamp": "2024-01-23T10:30:00.000Z"
        }
        assert processor._validate_webhook_payload(payload3) is False

    def test_validate_webhook_payload_missing_scan_id(self, processor):
        """Test validation fails for missing scan ID."""
        payload = {
            "eventType": "SCAN_COMPLETED",
            "timestamp": "2024-01-23T10:30:00.000Z",
            "scanData": {
                "projectId": "project-456"
                # Missing "id"
            }
        }
        
        assert processor._validate_webhook_payload(payload) is False

    @pytest.mark.asyncio
    @patch("webhook_processors.scan_webhook_processor.ocean")
    async def test_process_webhook_data_scan_completed(self, mock_ocean, processor):
        """Test processing SCAN_COMPLETED webhook."""
        # Arrange
        mock_ocean.register_raw = AsyncMock()
        
        payload = {
            "eventType": "SCAN_COMPLETED",
            "timestamp": "2024-01-23T10:30:00.000Z",
            "scanData": {
                "id": "scan-123",
                "projectId": "project-456", 
                "projectName": "test-project",
                "branch": "main",
                "engines": ["sast", "sca"],
                "sourceType": "git",
                "sourceOrigin": "https://github.com/test/repo.git",
                "initiator": "user@example.com",
                "createdAt": "2024-01-23T10:00:00.000Z",
                "tags": {"environment": "dev"}
            }
        }

        # Act
        result = await processor._process_webhook_data(payload)

        # Assert
        assert result is not None
        assert result["id"] == "scan-123"
        assert result["status"] == "Completed"
        assert result["projectId"] == "project-456"
        assert result["scanTypes"] == ["sast", "sca"]
        assert result["_webhook_event"]["type"] == "SCAN_COMPLETED"
        
        # Verify ocean.register_raw was called
        mock_ocean.register_raw.assert_called_once_with("scan", [result])

    @pytest.mark.asyncio
    async def test_process_webhook_data_unsupported_event(self, processor):
        """Test processing unsupported event type."""
        payload = {
            "eventType": "UNSUPPORTED_EVENT",
            "timestamp": "2024-01-23T10:30:00.000Z",
            "scanData": {
                "id": "scan-123"
            }
        }

        result = await processor._process_webhook_data(payload)
        assert result is None

    @pytest.mark.asyncio
    async def test_process_webhook_data_missing_scan_data(self, processor):
        """Test processing webhook with missing scan data."""
        payload = {
            "eventType": "SCAN_COMPLETED",
            "timestamp": "2024-01-23T10:30:00.000Z"
            # Missing scanData
        }

        result = await processor._process_webhook_data(payload)
        assert result is None