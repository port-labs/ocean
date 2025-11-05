import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aioresponses import aioresponses
import json

from harbor.clients.harbor_client import HarborClient


class TestHarborClient:
    """Test Harbor API client functionality."""
    
    @pytest.fixture
    def harbor_client(self):
        """Create Harbor client for testing."""
        return HarborClient(
            base_url="http://localhost:8081",
            username="admin",
            password="Harbor12345"
        )
    
    def test_client_initialization(self, harbor_client):
        """Test client initialization with correct parameters."""
        assert harbor_client.base_url == "http://localhost:8081"
        assert harbor_client.username == "admin"
        assert harbor_client.password == "Harbor12345"
        assert harbor_client.semaphore._value == 10  # Default max_concurrent_requests
    
    def test_headers_property(self, harbor_client):
        """Test authentication headers generation."""
        headers = harbor_client.headers
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["Content-Type"] == "application/json"
    
    @pytest.mark.asyncio
    async def test_get_projects_success(self, harbor_client, sample_project_data):
        """Test successful projects retrieval."""
        with aioresponses() as m:
            m.get(
                "http://localhost:8081/api/v2.0/projects",
                payload=sample_project_data
            )
            
            projects = await harbor_client.get_projects()
            assert len(projects) == 2
            assert projects[0]["name"] == "library"
            assert projects[1]["name"] == "opensource"
    
    @pytest.mark.asyncio
    async def test_get_projects_with_filters(self, harbor_client, sample_project_data):
        """Test projects retrieval with filters."""
        with aioresponses() as m:
            m.get(
                "http://localhost:8081/api/v2.0/projects",
                payload=sample_project_data
            )
            
            # Test visibility filter
            projects = await harbor_client.get_projects(visibility="public")
            assert len(projects) == 2  # Both are public in sample data
            
            # Test name prefix filter
            projects = await harbor_client.get_projects(name_prefix="lib")
            assert len(projects) == 1
            assert projects[0]["name"] == "library"
    
    @pytest.mark.asyncio
    async def test_get_users_success(self, harbor_client, sample_user_data):
        """Test successful users retrieval."""
        with aioresponses() as m:
            m.get(
                "http://localhost:8081/api/v2.0/users",
                payload=sample_user_data
            )
            
            users = await harbor_client.get_users()
            assert len(users) == 2
            assert users[0]["username"] == "admin"
            assert users[1]["username"] == "developer"
    
    @pytest.mark.asyncio
    async def test_get_users_with_filters(self, harbor_client, sample_user_data):
        """Test users retrieval with filters."""
        with aioresponses() as m:
            m.get(
                "http://localhost:8081/api/v2.0/users",
                payload=sample_user_data
            )
            
            # Test admin only filter
            users = await harbor_client.get_users(admin_only=True)
            assert len(users) == 1
            assert users[0]["username"] == "admin"
            
            # Test email domain filter
            users = await harbor_client.get_users(email_domain="company.com")
            assert len(users) == 1
            assert users[0]["username"] == "developer"
    
    @pytest.mark.asyncio
    async def test_get_repositories_success(self, harbor_client, sample_repository_data):
        """Test successful repositories retrieval."""
        with aioresponses() as m:
            m.get(
                "http://localhost:8081/api/v2.0/projects/opensource/repositories",
                payload=sample_repository_data
            )
            
            repos = await harbor_client.get_repositories("opensource")
            assert len(repos) == 2
            assert repos[0]["name"] == "opensource/nginx"
            assert repos[1]["name"] == "opensource/redis"
    
    @pytest.mark.asyncio
    async def test_get_artifacts_success(self, harbor_client, sample_artifact_data):
        """Test successful artifacts retrieval."""
        with aioresponses() as m:
            m.get(
                "http://localhost:8081/api/v2.0/projects/opensource/repositories/nginx/artifacts",
                payload=sample_artifact_data
            )
            
            artifacts = await harbor_client.get_artifacts("opensource", "nginx")
            assert len(artifacts) == 1
            assert artifacts[0]["digest"] == "sha256:1234567890abcdef"
    
    @pytest.mark.asyncio
    async def test_pagination(self, harbor_client, sample_project_data):
        """Test pagination functionality."""
        with aioresponses() as m:
            # First page
            m.get(
                "http://localhost:8081/api/v2.0/projects",
                payload=sample_project_data
            )
            # Second page (empty)
            m.get(
                "http://localhost:8081/api/v2.0/projects",
                payload=[]
            )
            
            all_projects = []
            async for projects_batch in harbor_client.get_paginated_projects():
                all_projects.extend(projects_batch)
                
            assert len(all_projects) == 2
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self, harbor_client):
        """Test API error handling."""
        with aioresponses() as m:
            m.get(
                "http://localhost:8081/api/v2.0/projects",
                status=401
            )
            
            with pytest.raises(Exception):
                await harbor_client.get_projects()
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, harbor_client):
        """Test rate limiting functionality."""
        harbor_client.rate_limit_delay = 0.01  # Small delay for testing
        
        with aioresponses() as m:
            m.get(
                "http://localhost:8081/api/v2.0/projects",
                payload=[]
            )
            
            import time
            start_time = time.time()
            await harbor_client.get_projects()
            end_time = time.time()
            
            # Should have at least the rate limit delay
            assert end_time - start_time >= 0.01