from typing import Any, Dict, Optional
from loguru import logger

from port_ocean.context.ocean import ocean
from webhook_processors.base_webhook_processor import BaseCheckmarxWebhookProcessor


@ocean.webhook("scan")
class ScanWebhookProcessor(BaseCheckmarxWebhookProcessor):
    """Webhook processor for Checkmarx One scan events."""

    SUPPORTED_EVENTS = [
        "SCAN_STARTED",
        "SCAN_COMPLETED", 
        "SCAN_FAILED",
        "SCAN_CANCELED"
    ]

    async def _process_webhook_data(self, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process scan webhook data.
        
        Args:
            body: The webhook payload body
            
        Returns:
            Processed scan entity data or None if not processable
        """
        event_type = body.get("eventType")
        
        if event_type not in self.SUPPORTED_EVENTS:
            logger.debug(f"Ignoring unsupported event type: {event_type}")
            return None
            
        scan_data = self._extract_entity_data(body, "scanData")
        
        if not scan_data:
            logger.error("No scan data found in webhook payload")
            return None
            
        # Extract key scan information
        scan_id = scan_data.get("id")
        if not scan_id:
            logger.error("No scan ID found in webhook payload")
            return None
            
        logger.info(f"Processing scan {event_type} event for scan ID: {scan_id}")
        
        # Enrich scan data with event context
        processed_data = {
            "id": scan_id,
            "status": self._map_event_to_status(event_type),
            "projectId": scan_data.get("projectId"),
            "projectName": scan_data.get("projectName"),
            "branch": scan_data.get("branch"),
            "engines": scan_data.get("engines", []),
            "sourceType": scan_data.get("sourceType"),
            "sourceOrigin": scan_data.get("sourceOrigin"),
            "initiator": scan_data.get("initiator"),
            "createdAt": scan_data.get("createdAt"),
            "updatedAt": body.get("timestamp"),  # Use webhook timestamp as update time
            "tags": scan_data.get("tags", {}),
            "scanTypes": [engine.lower() for engine in scan_data.get("engines", [])],
            "_webhook_event": {
                "type": event_type,
                "timestamp": body.get("timestamp")
            }
        }
        
        # Upsert the scan entity
        await ocean.register_raw("scan", [processed_data])
        
        return processed_data

    def _map_event_to_status(self, event_type: str) -> str:
        """
        Map webhook event type to scan status.
        
        Args:
            event_type: The webhook event type
            
        Returns:
            Mapped scan status
        """
        event_status_map = {
            "SCAN_STARTED": "Running",
            "SCAN_COMPLETED": "Completed",
            "SCAN_FAILED": "Failed", 
            "SCAN_CANCELED": "Canceled"
        }
        
        return event_status_map.get(event_type, "Unknown")

    def _validate_webhook_payload(self, body: Dict[str, Any]) -> bool:
        """
        Validate scan webhook payload.
        
        Args:
            body: The webhook payload body
            
        Returns:
            True if payload is valid, False otherwise
        """
        if not super()._validate_webhook_payload(body):
            return False
            
        # Additional scan-specific validation
        if "scanData" not in body:
            logger.error("Missing 'scanData' field in scan webhook payload")
            return False
            
        scan_data = body["scanData"]
        if not scan_data.get("id"):
            logger.error("Missing 'id' field in scanData")
            return False
            
        return True