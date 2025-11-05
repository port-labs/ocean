from typing import AsyncGenerator, List, Dict, Any
import asyncio
from loguru import logger
from harbor.clients.harbor_client import HarborClient
from harbor.helpers.metrics import IngestionStats


class BaseExporter:
    def __init__(self, client: HarborClient):
        self.client = client
        self.stats = IngestionStats()
        
    async def get_paginated_resources(self, selector: Dict[str, Any] = None) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Base method for paginated resource fetching with filtering support."""
        raise NotImplementedError("Subclasses must implement get_paginated_resources")


class ProjectExporter(BaseExporter):
    async def get_paginated_resources(self, selector: Dict[str, Any] = None) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.info("Starting Harbor projects export")
        filters = selector or {}
        
        try:
            async for projects_batch in self.client.get_paginated_projects(**filters):
                self.stats.projects_processed += len(projects_batch)
                logger.info(f"Yielding {len(projects_batch)} projects (total: {self.stats.projects_processed})")
                yield projects_batch
        except Exception as e:
            self.stats.projects_errors += 1
            logger.error(f"Error in projects export: {e}")
            raise
        finally:
            logger.info(f"Projects export completed: {self.stats.projects_processed} processed, {self.stats.projects_errors} errors")


class UserExporter(BaseExporter):
    async def get_paginated_resources(self, selector: Dict[str, Any] = None) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.info("Starting Harbor users export")
        filters = selector or {}
        
        try:
            async for users_batch in self.client.get_paginated_users(**filters):
                self.stats.users_processed += len(users_batch)
                logger.info(f"Yielding {len(users_batch)} users (total: {self.stats.users_processed})")
                yield users_batch
        except Exception as e:
            self.stats.users_errors += 1
            logger.error(f"Error in users export: {e}")
            raise
        finally:
            logger.info(f"Users export completed: {self.stats.users_processed} processed, {self.stats.users_errors} errors")


class RepositoryExporter(BaseExporter):
    async def get_paginated_resources(self, selector: Dict[str, Any] = None) -> AsyncGenerator[List[Dict[str, Any]], None]:
        filters = selector or {}
        project_name = filters.get("project_name")
        
        if project_name:
            projects = [{"name": project_name}]
        else:
            # Get all projects first
            projects = []
            async for projects_batch in self.client.get_paginated_projects():
                projects.extend(projects_batch)

        # Process projects in parallel batches
        batch_size = 5
        for i in range(0, len(projects), batch_size):
            project_batch = projects[i:i + batch_size]
            tasks = []
            
            for project in project_batch:
                task = self._fetch_project_repositories(project["name"], filters)
                tasks.append(task)
                
            # Execute batch in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    self.stats.repositories_errors += 1
                    logger.error(f"Error fetching repositories: {result}")
                    continue
                    
                async for repos_batch in result:
                    self.stats.repositories_processed += len(repos_batch)
                    logger.info(f"Yielding {len(repos_batch)} repositories (total: {self.stats.repositories_processed})")
                    yield repos_batch
                    
    async def _fetch_project_repositories(self, project_name: str, filters: Dict[str, Any]) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.info(f"Fetching repositories for project: {project_name}")
        
        async for repos_batch in self.client.get_paginated_repositories(project_name, **filters):
            # Add project context to each repository
            for repo in repos_batch:
                repo["project_name"] = project_name
            logger.info(f"Yielding {len(repos_batch)} repositories from project {project_name}")
            yield repos_batch


class ArtifactExporter(BaseExporter):
    async def get_paginated_resources(self, selector: Dict[str, Any] = None) -> AsyncGenerator[List[Dict[str, Any]], None]:
        filters = selector or {}
        project_name = filters.get("project_name")
        repository_name = filters.get("repository_name")
        
        if project_name and repository_name:
            repositories = [{"name": repository_name, "project_name": project_name}]
        else:
            # Get all repositories first
            repositories = []
            repo_exporter = RepositoryExporter(self.client)
            repo_filters = {k: v for k, v in filters.items() if k in ["project_name"]}
            async for repos_batch in repo_exporter.get_paginated_resources(repo_filters):
                repositories.extend(repos_batch)

        # Process repositories in parallel batches
        batch_size = 3  # Smaller batch for artifacts due to higher API load
        for i in range(0, len(repositories), batch_size):
            repo_batch = repositories[i:i + batch_size]
            tasks = []
            
            for repo in repo_batch:
                task = self._fetch_repository_artifacts(repo, filters)
                tasks.append(task)
                
            # Execute batch in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    self.stats.artifacts_errors += 1
                    logger.error(f"Error fetching artifacts: {result}")
                    continue
                    
                async for artifacts_batch in result:
                    self.stats.artifacts_processed += len(artifacts_batch)
                    logger.info(f"Yielding {len(artifacts_batch)} artifacts (total: {self.stats.artifacts_processed})")
                    yield artifacts_batch
                    
    async def _fetch_repository_artifacts(self, repo: Dict[str, Any], filters: Dict[str, Any]) -> AsyncGenerator[List[Dict[str, Any]], None]:
        project_name = repo["project_name"]
        repo_name = repo["name"].split("/")[-1]  # Extract repo name from full path
        logger.info(f"Fetching artifacts for {project_name}/{repo_name}")
        
        try:
            # Filter out repository-specific filters for artifact API
            artifact_filters = {k: v for k, v in filters.items() 
                              if k in ["tag_pattern", "created_since", "media_type", 
                                      "with_scan_results", "min_severity", "max_size_mb"]}
            
            async for artifacts_batch in self.client.get_paginated_artifacts(project_name, repo_name, **artifact_filters):
                # Add context to each artifact
                for artifact in artifacts_batch:
                    artifact["project_name"] = project_name
                    artifact["repository_name"] = repo_name
                logger.info(f"Yielding {len(artifacts_batch)} artifacts from {project_name}/{repo_name}")
                yield artifacts_batch
        except Exception as e:
            logger.warning(f"Failed to fetch artifacts for {project_name}/{repo_name}: {e}")
            return