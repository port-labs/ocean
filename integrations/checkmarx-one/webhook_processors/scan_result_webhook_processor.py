from typing import Any, Dict, Optional, List
from loguru import logger

from port_ocean.context.ocean import ocean
from webhook_processors.base_webhook_processor import BaseCheckmarxWebhookProcessor


@ocean.webhook("scan_result")
class ScanResultWebhookProcessor(BaseCheckmarxWebhookProcessor):
    """Webhook processor for Checkmarx One scan result events."""

    SUPPORTED_EVENTS = [
        "SCAN_RESULTS_READY",
        "VULNERABILITY_STATE_CHANGED",
        "VULNERABILITY_COMMENT_ADDED"
    ]

    async def _process_webhook_data(self, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process scan result webhook data.
        
        Args:
            body: The webhook payload body
            
        Returns:
            Processed scan result entity data or None if not processable
        """
        event_type = body.get("eventType")
        
        if event_type not in self.SUPPORTED_EVENTS:
            logger.debug(f"Ignoring unsupported event type: {event_type}")
            return None
            
        if event_type == "SCAN_RESULTS_READY":
            return await self._process_scan_results_ready(body)
        elif event_type in ["VULNERABILITY_STATE_CHANGED", "VULNERABILITY_COMMENT_ADDED"]:
            return await self._process_vulnerability_update(body)
            
        return None

    async def _process_scan_results_ready(self, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process scan results ready event.
        
        Args:
            body: The webhook payload body
            
        Returns:
            Processing summary
        """
        scan_data = self._extract_entity_data(body, "scanData")
        scan_id = scan_data.get("id")
        
        if not scan_id:
            logger.error("No scan ID found in SCAN_RESULTS_READY webhook")
            return None
            
        logger.info(f"Processing scan results ready for scan: {scan_id}")
        
        # Get scan results from webhook or trigger a sync
        results_data = body.get("resultsData", [])
        
        if results_data:
            processed_results = []
            for result in results_data:
                processed_result = self._process_single_result(result, scan_id)
                if processed_result:
                    processed_results.append(processed_result)
            
            if processed_results:
                await ocean.register_raw("scan_result", processed_results)
                logger.info(f"Processed {len(processed_results)} scan results for scan {scan_id}")
        
        return {
            "scan_id": scan_id,
            "results_count": len(results_data),
            "event_type": "SCAN_RESULTS_READY"
        }

    async def _process_vulnerability_update(self, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process vulnerability update events (state change or comment added).
        
        Args:
            body: The webhook payload body
            
        Returns:
            Processed vulnerability update data
        """
        vulnerability_data = self._extract_entity_data(body, "vulnerabilityData")
        
        if not vulnerability_data:
            logger.error("No vulnerability data found in webhook payload")
            return None
            
        result_id = vulnerability_data.get("id")
        if not result_id:
            logger.error("No vulnerability ID found in webhook payload")
            return None
            
        scan_id = vulnerability_data.get("scanId")
        event_type = body.get("eventType")
        
        logger.info(f"Processing {event_type} for vulnerability: {result_id}")
        
        processed_result = self._process_single_result(vulnerability_data, scan_id)
        if processed_result:
            processed_result["_webhook_event"] = {
                "type": event_type,
                "timestamp": body.get("timestamp"),
                "previous_state": body.get("previousState"),
                "new_comment": body.get("commentData") if event_type == "VULNERABILITY_COMMENT_ADDED" else None
            }
            
            await ocean.register_raw("scan_result", [processed_result])
            
        return processed_result

    def _process_single_result(self, result_data: Dict[str, Any], scan_id: str) -> Dict[str, Any]:
        """
        Process a single vulnerability result.
        
        Args:
            result_data: Individual result data
            scan_id: Associated scan ID
            
        Returns:
            Processed result data
        """
        return {
            "id": result_data.get("id"),
            "type": result_data.get("type", "").lower(),
            "severity": result_data.get("severity"),
            "state": result_data.get("state"),
            "status": result_data.get("status"),
            "data": result_data.get("data", {}),
            "description": result_data.get("description"),
            "similarityId": result_data.get("similarityId"),
            "cweId": result_data.get("cweId"),
            "cveId": result_data.get("cveId"),
            "vulnerabilityId": result_data.get("vulnerabilityId"),
            "packageData": result_data.get("packageData", {}),
            "created": result_data.get("created"),
            "firstFoundAt": result_data.get("firstFoundAt"),
            "foundAt": result_data.get("foundAt"),
            "firstScanId": result_data.get("firstScanId"),
            "comments": result_data.get("comments", []),
            "__scan_id": scan_id,
            "projectId": result_data.get("projectId")
        }

    def _validate_webhook_payload(self, body: Dict[str, Any]) -> bool:
        """
        Validate scan result webhook payload.
        
        Args:
            body: The webhook payload body
            
        Returns:
            True if payload is valid, False otherwise
        """
        if not super()._validate_webhook_payload(body):
            return False
            
        event_type = body.get("eventType")
        
        # Validate based on event type
        if event_type == "SCAN_RESULTS_READY":
            if "scanData" not in body:
                logger.error("Missing 'scanData' field in SCAN_RESULTS_READY webhook")
                return False
        elif event_type in ["VULNERABILITY_STATE_CHANGED", "VULNERABILITY_COMMENT_ADDED"]:
            if "vulnerabilityData" not in body:
                logger.error(f"Missing 'vulnerabilityData' field in {event_type} webhook")
                return False
                
        return True