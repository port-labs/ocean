from typing import Dict, Any, List
from loguru import logger

from harbor.webhook_processors.base_processor import BaseHarborWebhookProcessor
from harbor.helpers.webhook_utils import HarborEventType


class ArtifactWebhookProcessor(BaseHarborWebhookProcessor):
    """Process Harbor artifact-related webhook events."""
    
    async def _process_event(self, event_data: Dict[str, Any], resource_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process artifact events (push, pull, delete, scan)."""
        event_type = resource_info["event_type"]
        project_name = resource_info["project_name"]
        repository_name = resource_info["repository_name"]
        
        if not project_name or not repository_name:
            logger.warning(f"Missing project or repository info in event: {resource_info}")
            return []
            
        try:
            if event_type == HarborEventType.PUSH_ARTIFACT:
                return await self._handle_artifact_push(project_name, repository_name, resource_info)
            elif event_type == HarborEventType.DELETE_ARTIFACT:
                return await self._handle_artifact_delete(project_name, repository_name, resource_info)
            elif event_type in [HarborEventType.SCANNING_COMPLETED, HarborEventType.SCANNING_FAILED]:
                return await self._handle_scan_event(project_name, repository_name, resource_info)
            else:
                logger.debug(f"Ignoring artifact event type: {event_type}")
                return []
                
        except Exception as e:
            logger.error(f"Error processing artifact event {event_type}: {e}")
            return []
            
    async def _handle_artifact_push(self, project_name: str, repository_name: str, resource_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle artifact push events."""
        logger.info(f"Processing artifact push for {project_name}/{repository_name}")
        
        try:
            # Fetch the updated artifact data
            artifacts = []
            async for artifacts_batch in self.client.get_paginated_artifacts(project_name, repository_name):
                artifacts.extend(artifacts_batch)
                
            # Filter to the specific artifact if digest is available
            if resource_info.get("artifact_digest"):
                digest = resource_info["artifact_digest"]
                artifacts = [a for a in artifacts if a.get("digest") == digest]
                
            # Add context to artifacts
            for artifact in artifacts:
                artifact["project_name"] = project_name
                artifact["repository_name"] = repository_name
                
            logger.info(f"Fetched {len(artifacts)} artifacts for push event")
            return artifacts
            
        except Exception as e:
            logger.error(f"Error fetching artifacts for push event: {e}")
            return []
            
    async def _handle_artifact_delete(self, project_name: str, repository_name: str, resource_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle artifact delete events."""
        logger.info(f"Processing artifact delete for {project_name}/{repository_name}")
        
        # For delete events, we return empty list as the artifact no longer exists
        # The Ocean framework will handle the deletion based on the missing entity
        return []
        
    async def _handle_scan_event(self, project_name: str, repository_name: str, resource_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle vulnerability scan completion events."""
        event_type = resource_info["event_type"]
        logger.info(f"Processing scan event {event_type} for {project_name}/{repository_name}")
        
        try:
            # Fetch artifacts with updated scan results
            artifacts = []
            async for artifacts_batch in self.client.get_paginated_artifacts(
                project_name, repository_name, with_scan_results=True
            ):
                artifacts.extend(artifacts_batch)
                
            # Filter to the specific artifact if digest is available
            if resource_info.get("artifact_digest"):
                digest = resource_info["artifact_digest"]
                artifacts = [a for a in artifacts if a.get("digest") == digest]
                
            # Add context to artifacts
            for artifact in artifacts:
                artifact["project_name"] = project_name
                artifact["repository_name"] = repository_name
                
            logger.info(f"Fetched {len(artifacts)} artifacts with scan results")
            return artifacts
            
        except Exception as e:
            logger.error(f"Error fetching artifacts for scan event: {e}")
            return []