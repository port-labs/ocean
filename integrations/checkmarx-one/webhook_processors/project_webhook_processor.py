from typing import Any, Dict, Optional
from loguru import logger

from port_ocean.context.ocean import ocean
from webhook_processors.base_webhook_processor import BaseCheckmarxWebhookProcessor


@ocean.webhook("project")
class ProjectWebhookProcessor(BaseCheckmarxWebhookProcessor):
    """Webhook processor for Checkmarx One project events."""

    SUPPORTED_EVENTS = [
        "PROJECT_CREATED",
        "PROJECT_UPDATED",
        "PROJECT_DELETED"
    ]

    async def _process_webhook_data(self, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process project webhook data.
        
        Args:
            body: The webhook payload body
            
        Returns:
            Processed project entity data or None if not processable
        """
        event_type = body.get("eventType")
        
        if event_type not in self.SUPPORTED_EVENTS:
            logger.debug(f"Ignoring unsupported event type: {event_type}")
            return None
            
        project_data = self._extract_entity_data(body, "projectData")
        
        if not project_data:
            logger.error("No project data found in webhook payload")
            return None
            
        # Extract key project information
        project_id = project_data.get("id")
        if not project_id:
            logger.error("No project ID found in webhook payload")
            return None
            
        logger.info(f"Processing project {event_type} event for project ID: {project_id}")
        
        # Handle project deletion
        if event_type == "PROJECT_DELETED":
            logger.info(f"Deleting project entity: {project_id}")
            await ocean.unregister_raw("project", [{"id": project_id}])
            return {"id": project_id, "_deleted": True}
        
        # Process create/update events
        processed_data = {
            "id": project_id,
            "name": project_data.get("name"),
            "applicationIds": project_data.get("applicationIds", []),
            "repoUrl": project_data.get("repoUrl"),
            "mainBranch": project_data.get("mainBranch"),
            "origin": project_data.get("origin"),
            "tags": project_data.get("tags", {}),
            "groups": project_data.get("groups", []),
            "criticality": project_data.get("criticality"),
            "createdAt": project_data.get("createdAt"),
            "updatedAt": body.get("timestamp"),  # Use webhook timestamp as update time
            "_webhook_event": {
                "type": event_type,
                "timestamp": body.get("timestamp")
            }
        }
        
        # Upsert the project entity
        await ocean.register_raw("project", [processed_data])
        
        return processed_data

    def _validate_webhook_payload(self, body: Dict[str, Any]) -> bool:
        """
        Validate project webhook payload.
        
        Args:
            body: The webhook payload body
            
        Returns:
            True if payload is valid, False otherwise
        """
        if not super()._validate_webhook_payload(body):
            return False
            
        # Additional project-specific validation
        if "projectData" not in body:
            logger.error("Missing 'projectData' field in project webhook payload")
            return False
            
        project_data = body["projectData"]
        if not project_data.get("id"):
            logger.error("Missing 'id' field in projectData")
            return False
            
        return True