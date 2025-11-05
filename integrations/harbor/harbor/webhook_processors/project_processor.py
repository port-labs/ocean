from typing import Dict, Any, List
from loguru import logger

from harbor.webhook_processors.base_processor import BaseHarborWebhookProcessor
from harbor.helpers.webhook_utils import HarborEventType


class ProjectWebhookProcessor(BaseHarborWebhookProcessor):
    """Process Harbor project-related webhook events."""
    
    async def _process_event(self, event_data: Dict[str, Any], resource_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process project events."""
        event_type = resource_info["event_type"]
        project_name = resource_info["project_name"]
        
        if not project_name:
            logger.warning(f"Missing project info in event: {resource_info}")
            return []
            
        try:
            if event_type in [HarborEventType.PROJECT_QUOTA_EXCEED, HarborEventType.PROJECT_QUOTA_WARNING]:
                return await self._handle_project_quota_event(project_name)
            elif event_type in [HarborEventType.PUSH_ARTIFACT, HarborEventType.DELETE_ARTIFACT]:
                # Artifact changes affect project repository count
                return await self._handle_project_update(project_name)
            else:
                logger.debug(f"Ignoring project event type: {event_type}")
                return []
                
        except Exception as e:
            logger.error(f"Error processing project event {event_type}: {e}")
            return []
            
    async def _handle_project_quota_event(self, project_name: str) -> List[Dict[str, Any]]:
        """Handle project quota events."""
        logger.info(f"Processing project quota event for {project_name}")
        
        try:
            # Fetch updated project data
            projects = await self.client.get_projects(name=project_name)
            
            if not projects:
                logger.warning(f"Project {project_name} not found")
                return []
                
            logger.info(f"Fetched project data for quota event: {project_name}")
            return projects
            
        except Exception as e:
            logger.error(f"Error fetching project for quota event: {e}")
            return []
            
    async def _handle_project_update(self, project_name: str) -> List[Dict[str, Any]]:
        """Handle project updates (repository count changes)."""
        logger.info(f"Processing project update for {project_name}")
        
        try:
            # Fetch updated project data
            projects = await self.client.get_projects(name=project_name)
            
            if not projects:
                logger.warning(f"Project {project_name} not found")
                return []
                
            logger.info(f"Fetched updated project data: {project_name}")
            return projects
            
        except Exception as e:
            logger.error(f"Error fetching project for update: {e}")
            return []