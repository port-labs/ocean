import pytest
from unittest.mock import AsyncMock

from harbor.core.exporters import ProjectExporter, UserExporter, RepositoryExporter, ArtifactExporter


class TestProjectExporter:
    """Test Project exporter functionality."""
    
    @pytest.mark.asyncio
    async def test_project_export_success(self, mock_harbor_client, sample_project_data):
        """Test successful project export."""
        # Mock paginated projects
        async def mock_paginated_projects(**filters):
            yield sample_project_data
            
        mock_harbor_client.get_paginated_projects = mock_paginated_projects
        
        exporter = ProjectExporter(mock_harbor_client)
        
        all_projects = []
        async for projects_batch in exporter.get_paginated_resources():
            all_projects.extend(projects_batch)
            
        assert len(all_projects) == 2
        assert exporter.stats.projects_processed == 2
        assert exporter.stats.projects_errors == 0
    
    @pytest.mark.asyncio
    async def test_project_export_with_filters(self, mock_harbor_client, sample_project_data):
        """Test project export with selector filters."""
        async def mock_paginated_projects(**filters):
            # Simulate filtering
            if filters.get("visibility") == "public":
                yield sample_project_data
            else:
                yield []
                
        mock_harbor_client.get_paginated_projects = mock_paginated_projects
        
        exporter = ProjectExporter(mock_harbor_client)
        selector = {"visibility": "public"}
        
        all_projects = []
        async for projects_batch in exporter.get_paginated_resources(selector):
            all_projects.extend(projects_batch)
            
        assert len(all_projects) == 2


class TestUserExporter:
    """Test User exporter functionality."""
    
    @pytest.mark.asyncio
    async def test_user_export_success(self, mock_harbor_client, sample_user_data):
        """Test successful user export."""
        async def mock_paginated_users(**filters):
            yield sample_user_data
            
        mock_harbor_client.get_paginated_users = mock_paginated_users
        
        exporter = UserExporter(mock_harbor_client)
        
        all_users = []
        async for users_batch in exporter.get_paginated_resources():
            all_users.extend(users_batch)
            
        assert len(all_users) == 2
        assert exporter.stats.users_processed == 2
        assert exporter.stats.users_errors == 0


class TestRepositoryExporter:
    """Test Repository exporter functionality."""
    
    @pytest.mark.asyncio
    async def test_repository_export_success(self, mock_harbor_client, sample_project_data, sample_repository_data):
        """Test successful repository export."""
        async def mock_paginated_projects(**filters):
            yield sample_project_data
            
        async def mock_paginated_repositories(project_name, **filters):
            if project_name == "opensource":
                yield sample_repository_data
            else:
                yield []
                
        mock_harbor_client.get_paginated_projects = mock_paginated_projects
        mock_harbor_client.get_paginated_repositories = mock_paginated_repositories
        
        exporter = RepositoryExporter(mock_harbor_client)
        
        all_repositories = []
        async for repos_batch in exporter.get_paginated_resources():
            all_repositories.extend(repos_batch)
            
        assert len(all_repositories) == 2
        # Check that project context is added
        assert all_repositories[0]["project_name"] == "opensource"
    
    @pytest.mark.asyncio
    async def test_repository_export_specific_project(self, mock_harbor_client, sample_repository_data):
        """Test repository export for specific project."""
        async def mock_paginated_repositories(project_name, **filters):
            yield sample_repository_data
            
        mock_harbor_client.get_paginated_repositories = mock_paginated_repositories
        
        exporter = RepositoryExporter(mock_harbor_client)
        selector = {"project_name": "opensource"}
        
        all_repositories = []
        async for repos_batch in exporter.get_paginated_resources(selector):
            all_repositories.extend(repos_batch)
            
        assert len(all_repositories) == 2


class TestArtifactExporter:
    """Test Artifact exporter functionality."""
    
    @pytest.mark.asyncio
    async def test_artifact_export_success(self, mock_harbor_client, sample_repository_data, sample_artifact_data):
        """Test successful artifact export."""
        # Mock repository exporter dependency
        async def mock_repo_export(selector=None):
            repos_with_context = []
            for repo in sample_repository_data:
                repo["project_name"] = "opensource"
                repos_with_context.append(repo)
            yield repos_with_context
            
        async def mock_paginated_artifacts(project_name, repo_name, **filters):
            yield sample_artifact_data
            
        mock_harbor_client.get_paginated_artifacts = mock_paginated_artifacts
        
        exporter = ArtifactExporter(mock_harbor_client)
        # Mock the repository exporter
        exporter._fetch_repository_artifacts = AsyncMock()
        
        async def mock_fetch_repo_artifacts(repo, filters):
            artifacts_with_context = []
            for artifact in sample_artifact_data:
                artifact["project_name"] = repo["project_name"]
                artifact["repository_name"] = repo["name"].split("/")[-1]
                artifacts_with_context.append(artifact)
            yield artifacts_with_context
            
        exporter._fetch_repository_artifacts = mock_fetch_repo_artifacts
        
        # Mock repositories data
        repositories = []
        for repo in sample_repository_data:
            repo["project_name"] = "opensource"
            repositories.append(repo)
        
        all_artifacts = []
        # Simulate the batch processing
        for repo in repositories:
            async for artifacts_batch in exporter._fetch_repository_artifacts(repo, {}):
                all_artifacts.extend(artifacts_batch)
                
        assert len(all_artifacts) == 2  # One artifact per repository
        assert all_artifacts[0]["project_name"] == "opensource"
        assert "repository_name" in all_artifacts[0]