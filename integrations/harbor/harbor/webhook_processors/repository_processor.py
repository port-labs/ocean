from typing import Dict, Any, List
from loguru import logger

from harbor.webhook_processors.base_processor import BaseHarborWebhookProcessor
from harbor.helpers.webhook_utils import HarborEventType


class RepositoryWebhookProcessor(BaseHarborWebhookProcessor):
    """Process Harbor repository-related webhook events."""
    
    async def _process_event(self, event_data: Dict[str, Any], resource_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process repository events."""
        event_type = resource_info["event_type"]
        project_name = resource_info["project_name"]
        repository_name = resource_info["repository_name"]
        
        if not project_name:
            logger.warning(f"Missing project info in event: {resource_info}")
            return []
            
        try:
            # Repository events are typically triggered by artifact changes
            # We update the repository metadata (artifact count, pull count, etc.)
            if event_type in [HarborEventType.PUSH_ARTIFACT, HarborEventType.PULL_ARTIFACT]:
                return await self._handle_repository_update(project_name, repository_name)
            else:
                logger.debug(f"Ignoring repository event type: {event_type}")
                return []
                
        except Exception as e:
            logger.error(f"Error processing repository event {event_type}: {e}")
            return []
            
    async def _handle_repository_update(self, project_name: str, repository_name: str = None) -> List[Dict[str, Any]]:
        """Handle repository updates (artifact count, pull count changes)."""
        logger.info(f"Processing repository update for project {project_name}")
        
        try:
            repositories = []
            
            if repository_name:
                # Update specific repository
                async for repos_batch in self.client.get_paginated_repositories(project_name):
                    for repo in repos_batch:
                        repo_short_name = repo["name"].split("/")[-1]
                        if repo_short_name == repository_name:
                            repo["project_name"] = project_name
                            repositories.append(repo)
                            break
            else:
                # Update all repositories in the project
                async for repos_batch in self.client.get_paginated_repositories(project_name):
                    for repo in repos_batch:
                        repo["project_name"] = project_name
                    repositories.extend(repos_batch)
                    
            logger.info(f"Fetched {len(repositories)} repositories for update")
            return repositories
            
        except Exception as e:
            logger.error(f"Error fetching repositories for update: {e}")
            return []